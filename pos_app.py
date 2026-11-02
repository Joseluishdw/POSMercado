import tkinter as tk
from datetime import datetime
from tkinter import ttk, messagebox

import customtkinter as ctk
import qrcode
from PIL import Image, ImageDraw, ImageFont
from mysql.connector import Error

import config
from calculos import calcular_importe, calcular_totales, moneda
from db import BaseDatosPOS, ER_CHECK_CONSTRAINT_VIOLATED

# Colores de la interfaz
BG = "#0b1120"
PANEL = "#111a2e"
PANEL_2 = "#0f172a"
BORDE = "#1e2a44"
TEXTO = "#e2e8f0"
TENUE = "#94a3b8"
AZUL = "#2563eb"
AZUL_HOVER = "#1d4ed8"
VERDE = "#10b981"
VERDE_HOVER = "#059669"
ROJO = "#b91c1c"
ROJO_HOVER = "#991b1b"
AMBAR = "#f59e0b"
FUENTE = "Segoe UI"


class PuntoDeVentaApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        self.title("Punto de Venta")
        self.geometry("1360x820")
        self.minsize(1200, 740)
        self.configure(fg_color=BG)

        self.db = BaseDatosPOS()
        self.carrito = {}
        self.ticket_confirmado = False
        self.folio_estimado = 1
        self._qr_ctk = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._estilo_treeview()
        self._construir_encabezado()
        self._construir_kpis()
        self._construir_cuerpo()
        self._atajos()

        self._mostrar_qr_placeholder()
        self._actualizar_totales()
        self._actualizar_reloj()
        self.after(200, self._conectar_bd)

    # Estilo de la tabla de productos
    def _estilo_treeview(self):
        estilo = ttk.Style(self)
        estilo.theme_use("clam")
        estilo.configure(
            "POS.Treeview",
            background=PANEL_2, fieldbackground=PANEL_2, foreground=TEXTO,
            rowheight=36, borderwidth=0, font=(FUENTE, 12),
        )
        estilo.configure(
            "POS.Treeview.Heading",
            background="#0a1324", foreground=TENUE, relief="flat",
            font=(FUENTE, 11, "bold"), padding=(8, 8),
        )
        estilo.map("POS.Treeview.Heading", background=[("active", "#132040")])
        estilo.map("POS.Treeview", background=[("selected", AZUL)], foreground=[("selected", "white")])
        estilo.layout("POS.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

    def _tarjeta(self, padre, **kw):
        return ctk.CTkFrame(padre, fg_color=PANEL, corner_radius=14,
                            border_width=1, border_color=BORDE, **kw)

    # Encabezado con titulo, estado de MySQL, folio, fecha y empleado
    def _construir_encabezado(self):
        enc = self._tarjeta(self)
        enc.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 8))
        enc.grid_columnconfigure(0, weight=1)

        izq = ctk.CTkFrame(enc, fg_color="transparent")
        izq.grid(row=0, column=0, sticky="w", padx=18, pady=12)

        titulo = ctk.CTkFrame(izq, fg_color="transparent")
        titulo.pack(anchor="w")
        ctk.CTkLabel(titulo, text="🛒  PUNTO DE VENTA", font=(FUENTE, 26, "bold"),
                     text_color=TEXTO).pack(side="left")

        estado = ctk.CTkFrame(izq, fg_color="transparent")
        estado.pack(anchor="w", pady=(2, 0))
        self.lbl_estado = ctk.CTkLabel(estado, text="● CONECTANDO A MYSQL...",
                                       font=(FUENTE, 12, "bold"), text_color=AMBAR)
        self.lbl_estado.pack(side="left")
        self.btn_reconectar = ctk.CTkButton(
            estado, text="Reconectar", width=90, height=24, font=(FUENTE, 11),
            fg_color="#1e293b", hover_color="#334155", command=self._conectar_bd)
        self.btn_reconectar.pack(side="left", padx=10)

        der = ctk.CTkFrame(enc, fg_color="transparent")
        der.grid(row=0, column=1, sticky="e", padx=18, pady=12)
        self.lbl_folio = self._caja_info(der, "FOLIO", "#00001")
        self.lbl_fecha = self._caja_info(der, "FECHA", "--/--/---- --:--")
        self.lbl_empleado = self._caja_info(der, "EMPLEADO", config.EMPLEADO)

    def _caja_info(self, padre, titulo, valor):
        caja = ctk.CTkFrame(padre, fg_color=PANEL_2, corner_radius=10,
                            border_width=1, border_color=BORDE)
        caja.pack(side="left", padx=5)
        ctk.CTkLabel(caja, text=titulo, font=(FUENTE, 10, "bold"),
                     text_color=TENUE).pack(anchor="w", padx=14, pady=(8, 0))
        lbl = ctk.CTkLabel(caja, text=valor, font=(FUENTE, 15, "bold"), text_color=TEXTO)
        lbl.pack(anchor="w", padx=14, pady=(0, 8))
        return lbl

    # Tarjetas de indicadores (total de ventas, promedio y compras)
    def _construir_kpis(self):
        barra = ctk.CTkFrame(self, fg_color="transparent")
        barra.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 8))
        for i in range(3):
            barra.grid_columnconfigure(i, weight=1, uniform="kpi")

        self.kpi_total = self._tarjeta_kpi(barra, 0, "💰  TOTAL DE VENTAS ACUMULADO",
                                           "Σ Total Ticket de ventas confirmadas", VERDE)
        self.kpi_promedio = self._tarjeta_kpi(barra, 1, "📊  PROMEDIO DE TICKET",
                                              "V̄ = Σ Total Ticket ÷ m", "#60a5fa")
        self.kpi_compras = self._tarjeta_kpi(barra, 2, "✅  COMPRAS CONFIRMADAS",
                                             "Transacciones con COMMIT en VENTAS", "#c084fc")

    def _tarjeta_kpi(self, padre, col, titulo, pie, color):
        t = self._tarjeta(padre)
        t.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 6, 0 if col == 2 else 6))
        ctk.CTkFrame(t, fg_color=color, width=5, height=10, corner_radius=3).pack(side="left", fill="y", padx=(10, 0), pady=12)
        cont = ctk.CTkFrame(t, fg_color="transparent")
        cont.pack(side="left", fill="both", expand=True, padx=12, pady=8)
        ctk.CTkLabel(cont, text=titulo, font=(FUENTE, 11, "bold"), text_color=TENUE).pack(anchor="w")
        valor = ctk.CTkLabel(cont, text="—", font=(FUENTE, 24, "bold"), text_color=TEXTO)
        valor.pack(anchor="w")
        ctk.CTkLabel(cont, text=pie, font=(FUENTE, 10), text_color="#64748b").pack(anchor="w")
        return valor

    def _construir_cuerpo(self):
        cuerpo = ctk.CTkFrame(self, fg_color="transparent")
        cuerpo.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 14))
        cuerpo.grid_columnconfigure(0, weight=1)
        cuerpo.grid_columnconfigure(1, weight=0, minsize=360)
        cuerpo.grid_rowconfigure(0, weight=1)

        self._construir_columna_izquierda(cuerpo)
        self._construir_columna_derecha(cuerpo)

    # Columna izquierda: lector de codigo de barras, tabla y botones
    def _construir_columna_izquierda(self, padre):
        izq = ctk.CTkFrame(padre, fg_color="transparent")
        izq.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        izq.grid_columnconfigure(0, weight=1)
        izq.grid_rowconfigure(1, weight=1)

        # Campo para capturar codigo de barras
        cap = self._tarjeta(izq)
        cap.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        cap.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(cap, text="CAPTURAR CÓDIGO DE BARRAS",
                     font=(FUENTE, 12, "bold"), text_color=TENUE
                     ).grid(row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(12, 4))
        self.entry_codigo = ctk.CTkEntry(
            cap, height=60, font=("Consolas", 32, "bold"), fg_color=PANEL_2,
            border_color=AZUL, border_width=2, text_color="white",
            placeholder_text="7622202825682", corner_radius=10)
        self.entry_codigo.grid(row=1, column=0, sticky="ew", padx=(16, 10), pady=(0, 14))
        self.entry_codigo.bind("<Return>", self.agregar_por_codigo)
        self.entry_codigo.bind("<KP_Enter>", self.agregar_por_codigo)
        ctk.CTkButton(
            cap, text="🔍  Buscar / Agregar", width=190, height=60,
            font=(FUENTE, 14, "bold"), fg_color=AZUL, hover_color=AZUL_HOVER,
            corner_radius=10, command=self.agregar_por_codigo
        ).grid(row=1, column=1, padx=(0, 16), pady=(0, 14))

        # Tabla (GRID) de productos
        grid_card = self._tarjeta(izq)
        grid_card.grid(row=1, column=0, sticky="nsew")
        grid_card.grid_columnconfigure(0, weight=1)
        grid_card.grid_rowconfigure(0, weight=1)

        marco_tabla = tk.Frame(grid_card, bg=PANEL_2, highlightthickness=0)
        marco_tabla.grid(row=0, column=0, sticky="nsew", padx=12, pady=(12, 6))
        marco_tabla.grid_columnconfigure(0, weight=1)
        marco_tabla.grid_rowconfigure(0, weight=1)

        columnas = ("clave", "descripcion", "precio", "cantidad", "importe")
        self.tabla = ttk.Treeview(marco_tabla, columns=columnas, show="headings",
                                  style="POS.Treeview", selectmode="browse")
        encabezados = {
            "clave": ("CLAVE", 170, "w"),
            "descripcion": ("PRODUCTO / DESCRIPCIÓN", 300, "w"),
            "precio": ("PRECIO", 110, "e"),
            "cantidad": ("CANTIDAD", 100, "center"),
            "importe": ("IMPORTE", 120, "e"),
        }
        for col, (texto, ancho, ancla) in encabezados.items():
            self.tabla.heading(col, text=texto, anchor=ancla)
            self.tabla.column(col, width=ancho, anchor=ancla, stretch=(col == "descripcion"))
        self.tabla.tag_configure("impar", background="#13203a")
        self.tabla.tag_configure("par", background=PANEL_2)
        self.tabla.tag_configure("sin_stock", foreground=AMBAR)
        self.tabla.grid(row=0, column=0, sticky="nsew")
        self.tabla.bind("<Double-1>", self._editar_cantidad)
        self.tabla.bind("<Delete>", lambda e: self.quitar_articulo())

        scroll = ctk.CTkScrollbar(marco_tabla, command=self.tabla.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.tabla.configure(yscrollcommand=scroll.set)

        controles = ctk.CTkFrame(grid_card, fg_color="transparent")
        controles.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))
        estilo_btn = dict(height=32, font=(FUENTE, 12, "bold"), corner_radius=8,
                          fg_color="#1e293b", hover_color="#334155")
        ctk.CTkButton(controles, text="＋ Cantidad", width=110,
                      command=lambda: self.cambiar_cantidad(+1), **estilo_btn).pack(side="left", padx=(0, 6))
        ctk.CTkButton(controles, text="－ Cantidad", width=110,
                      command=lambda: self.cambiar_cantidad(-1), **estilo_btn).pack(side="left", padx=6)
        ctk.CTkButton(controles, text="🗑 Quitar artículo", width=140,
                      command=self.quitar_articulo, **estilo_btn).pack(side="left", padx=6)
        self.lbl_articulos = ctk.CTkLabel(controles, text="0 artículos", font=(FUENTE, 12),
                                          text_color=TENUE)
        self.lbl_articulos.pack(side="right")

        # Botones de guardar y cancelar venta
        acciones = ctk.CTkFrame(izq, fg_color="transparent")
        acciones.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        acciones.grid_columnconfigure((0, 1), weight=1, uniform="acc")
        ctk.CTkButton(
            acciones, text="💾  GUARDAR VENTA", height=56,
            font=(FUENTE, 16, "bold"), fg_color=VERDE, hover_color=VERDE_HOVER,
            corner_radius=12, command=self.guardar_venta
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(
            acciones, text="🗑  CANCELAR VENTA", height=56,
            font=(FUENTE, 16, "bold"), fg_color=ROJO, hover_color=ROJO_HOVER,
            corner_radius=12, command=self.cancelar_venta
        ).grid(row=0, column=1, sticky="ew", padx=(6, 0))

    # Columna derecha: vista del ticket con QR y totales
    def _construir_columna_derecha(self, padre):
        der = self._tarjeta(padre, width=360)
        der.grid(row=0, column=1, sticky="nsew")
        der.grid_propagate(False)
        der.grid_columnconfigure(0, weight=1)
        der.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(der, text="TICKET PREVIEW", font=(FUENTE, 12, "bold"),
                     text_color=TENUE).grid(row=0, column=0, pady=(8, 2))

        ticket = ctk.CTkFrame(der, fg_color="white", corner_radius=10)
        ticket.grid(row=1, column=0, padx=14, sticky="ew")
        self.lbl_qr = ctk.CTkLabel(ticket, text="")
        self.lbl_qr.pack(side="left", padx=(8, 4), pady=8)
        self.lbl_ticket = ctk.CTkLabel(ticket, text="", font=("Consolas", 11),
                                       text_color="#0f172a", justify="left", anchor="w")
        self.lbl_ticket.pack(side="left", fill="x", expand=True, padx=(4, 8), pady=8)

        totales = ctk.CTkFrame(der, fg_color="transparent")
        totales.grid(row=2, column=0, padx=16, pady=(8, 0), sticky="ew")
        totales.grid_columnconfigure(1, weight=1)
        self.lbl_subtotal = self._fila_total(totales, 0, "SUBTOTAL:", 20, TEXTO)
        self.lbl_iva = self._fila_total(totales, 1, "IVA:", 20, TEXTO)
        ctk.CTkFrame(totales, fg_color=BORDE, height=2).grid(row=2, column=0, columnspan=2, sticky="ew", pady=4)
        self.lbl_total = self._fila_total(totales, 3, "TOTAL:", 32, "#34d399")

        modo = ctk.CTkFrame(der, fg_color="#052e1f", corner_radius=10,
                            border_width=1, border_color="#065f46")
        modo.grid(row=4, column=0, padx=14, pady=(4, 12), sticky="ew")
        ctk.CTkLabel(modo, text="●  MODO TRANSACCIONAL ACTIVO", font=(FUENTE, 11, "bold"),
                     text_color="#34d399").pack(anchor="w", padx=10, pady=(4, 0))
        ctk.CTkLabel(modo, text="Afecta VENTAS, PRODUCTOS y DETALLES_VENTA",
                     font=(FUENTE, 10), text_color="#a7f3d0", justify="left"
                     ).pack(anchor="w", padx=10, pady=(0, 4))

    def _fila_total(self, padre, fila, texto, tam, color):
        ctk.CTkLabel(padre, text=texto, font=(FUENTE, tam - 6, "bold"),
                     text_color=TENUE).grid(row=fila, column=0, sticky="w")
        lbl = ctk.CTkLabel(padre, text="$0.00", font=(FUENTE, tam, "bold"), text_color=color)
        lbl.grid(row=fila, column=1, sticky="e")
        return lbl

    def _atajos(self):
        self.bind("<F12>", self.guardar_venta)
        self.bind("<Escape>", self.cancelar_venta)

    def _enfocar(self):
        self.entry_codigo.focus_set()

    def _actualizar_reloj(self):
        self.lbl_fecha.configure(text=datetime.now().strftime("%d/%m/%Y %H:%M"))
        self.after(15000, self._actualizar_reloj)

    # Conecta a MySQL y carga los indicadores iniciales
    def _conectar_bd(self):
        try:
            self.db.conectar()
        except Error as e:
            self.lbl_estado.configure(text="● SIN CONEXIÓN A MYSQL", text_color="#f87171")
            messagebox.showerror("Error de conexión", f"No se pudo conectar a MySQL:\n{e}")
            self._enfocar()
            return
        self.lbl_estado.configure(text="● CONECTADO A MYSQL", text_color="#34d399")
        self._actualizar_kpis()
        self._enfocar()

    def _verificar_conexion(self):
        if self.db.esta_conectado():
            return True
        try:
            self.db.conectar()
            return True
        except Error:
            self.lbl_estado.configure(text="● SIN CONEXIÓN A MYSQL", text_color="#f87171")
            messagebox.showerror("Sin conexión", "No hay conexión con MySQL.")
            return False

    def _actualizar_kpis(self):
        try:
            total, promedio, compras = self.db.obtener_kpis()
            self.folio_estimado = self.db.siguiente_folio()
        except Error as e:
            messagebox.showerror("Error", str(e))
            return
        self.kpi_total.configure(text=f"{moneda(total)} MXN")
        self.kpi_promedio.configure(text=f"{moneda(promedio)} MXN / ticket")
        self.kpi_compras.configure(text=f"{compras} ticket{'s' if compras != 1 else ''}")
        if not self.ticket_confirmado:
            self.lbl_folio.configure(text=f"#{self.folio_estimado:05d}")
            self._actualizar_ticket_preview()

    # Genera la imagen del QR cuando se confirma una venta
    def _mostrar_qr_placeholder(self):
        img = Image.new("RGB", (200, 200), "#f1f5f9")
        d = ImageDraw.Draw(img)
        d.rectangle((6, 6, 193, 193), outline="#cbd5e1", width=3)
        for x, y in ((14, 14), (136, 14), (14, 136)):
            d.rectangle((x, y, x + 50, y + 50), outline="#cbd5e1", width=8)
        try:
            fuente = ImageFont.load_default(size=24)
        except TypeError:
            fuente = ImageFont.load_default()
        d.text((100, 100), "QR al\nconfirmar", fill="#64748b", anchor="mm",
               align="center", font=fuente)
        self._poner_imagen_qr(img)

    def _mostrar_qr(self, cadena):
        qr = qrcode.QRCode(box_size=8, border=2, error_correction=qrcode.constants.ERROR_CORRECT_M)
        qr.add_data(cadena)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        self._poner_imagen_qr(img)

    def _poner_imagen_qr(self, img):
        self._qr_ctk = ctk.CTkImage(light_image=img, dark_image=img, size=(120, 120))
        self.lbl_qr.configure(image=self._qr_ctk)

    def _actualizar_ticket_preview(self, folio=None, fecha=None, total=None, articulos=None):
        if folio is None:
            _, _, total = self._totales_carrito()
            articulos = sum(p["cantidad"] for p in self.carrito.values())
            art_txt = "1 artículo" if articulos == 1 else f"{articulos} artículos"
            texto = (f"EN CAPTURA...\n"
                     f"FOLIO #{self.folio_estimado:05d}\n"
                     f"{datetime.now():%d/%m/%Y %H:%M}\n"
                     f"{config.EMPLEADO}\n"
                     f"{art_txt}\n"
                     f"TOTAL {moneda(total)}")
        else:
            art_txt = "1 artículo" if articulos == 1 else f"{articulos} artículos"
            texto = (f"✔ CONFIRMADA\n"
                     f"FOLIO #{folio:05d}\n"
                     f"{fecha:%d/%m/%Y %H:%M}\n"
                     f"{config.EMPLEADO}\n"
                     f"{art_txt}\n"
                     f"TOTAL {moneda(total)}")
        self.lbl_ticket.configure(text=texto)

    def _totales_carrito(self):
        importes = [calcular_importe(p["precio"], p["cantidad"]) for p in self.carrito.values()]
        return calcular_totales(importes)

    def _salir_de_ticket_confirmado(self):
        if self.ticket_confirmado:
            self.ticket_confirmado = False
            self._mostrar_qr_placeholder()
            self.lbl_folio.configure(text=f"#{self.folio_estimado:05d}")

    # Actualiza las filas de la tabla y recalcula los totales
    def _refrescar_grid(self, seleccionar=None):
        self.tabla.delete(*self.tabla.get_children())
        for i, p in enumerate(self.carrito.values()):
            importe = calcular_importe(p["precio"], p["cantidad"])
            tags = ["impar" if i % 2 else "par"]
            if p["cantidad"] > p["stock"]:
                tags.append("sin_stock")
            self.tabla.insert("", "end", iid=p["clave"], tags=tags, values=(
                p["clave"], p["descripcion"], moneda(p["precio"]), p["cantidad"], moneda(importe)))
        if seleccionar and self.tabla.exists(seleccionar):
            self.tabla.selection_set(seleccionar)
            self.tabla.see(seleccionar)
        self._actualizar_totales()

    def _actualizar_totales(self):
        subtotal, iva, total = self._totales_carrito()
        self.lbl_subtotal.configure(text=moneda(subtotal))
        self.lbl_iva.configure(text=moneda(iva))
        self.lbl_total.configure(text=moneda(total))
        n = sum(p["cantidad"] for p in self.carrito.values())
        renglones_txt = "1 renglón" if len(self.carrito) == 1 else f"{len(self.carrito)} renglones"
        art_txt = "1 artículo" if n == 1 else f"{n} artículos"
        self.lbl_articulos.configure(text=f"{art_txt} · {renglones_txt}")
        self._actualizar_ticket_preview()

    # Busca el producto por codigo de barras y lo agrega a la tabla
    def agregar_por_codigo(self, event=None):
        codigo = self.entry_codigo.get().strip()
        if not codigo:
            return "break"
        if not self._verificar_conexion():
            return "break"
        try:
            producto = self.db.buscar_producto(codigo)
        except Error as e:
            messagebox.showerror("Error", str(e))
            return "break"

        self.entry_codigo.delete(0, "end")
        if producto is None:
            messagebox.showwarning("Producto no encontrado",
                                   f"No existe ningún artículo con la clave:\n{codigo}")
            self._enfocar()
            return "break"

        self._salir_de_ticket_confirmado()
        clave = producto["clave"]
        if clave in self.carrito:
            self.carrito[clave]["cantidad"] += 1
            self.carrito[clave]["stock"] = producto["stock"]
        else:
            self.carrito[clave] = {
                "clave": clave,
                "descripcion": producto["descripcion"],
                "precio": producto["precio"],
                "cantidad": 1,
                "stock": producto["stock"],
            }
        self._refrescar_grid(seleccionar=clave)
        self._enfocar()
        return "break"

    def _clave_seleccionada(self):
        sel = self.tabla.selection()
        if not sel:
            messagebox.showinfo("Aviso", "Selecciona un producto de la tabla.")
            self._enfocar()
            return None
        return sel[0]

    def cambiar_cantidad(self, delta):
        clave = self._clave_seleccionada()
        if clave is None:
            return
        nueva = self.carrito[clave]["cantidad"] + delta
        if nueva <= 0:
            del self.carrito[clave]
            clave = None
        else:
            self.carrito[clave]["cantidad"] = nueva
        self._refrescar_grid(seleccionar=clave)
        self._enfocar()

    def _editar_cantidad(self, event=None):
        fila = self.tabla.identify_row(event.y) if event else None
        if not fila:
            return
        dialogo = ctk.CTkInputDialog(title="Cambiar cantidad",
                                     text=f"Nueva cantidad para:\n{self.carrito[fila]['descripcion']}")
        valor = dialogo.get_input()
        if valor is None:
            self._enfocar()
            return
        try:
            cantidad = int(valor)
            if cantidad < 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Cantidad inválida", "Escribe un número entero mayor o igual a 0.")
            self._enfocar()
            return
        if cantidad == 0:
            del self.carrito[fila]
            fila = None
        else:
            self.carrito[fila]["cantidad"] = cantidad
        self._refrescar_grid(seleccionar=fila)
        self._enfocar()

    def quitar_articulo(self):
        clave = self._clave_seleccionada()
        if clave is None:
            return
        del self.carrito[clave]
        self._refrescar_grid()
        self._enfocar()

    # Guarda la venta ejecutando la transaccion en las 3 tablas
    def guardar_venta(self, event=None):
        if not self.carrito:
            messagebox.showwarning("Venta vacía", "Agrega al menos un producto antes de guardar.")
            self._enfocar()
            return
        if not self._verificar_conexion():
            return

        subtotal, iva, total = self._totales_carrito()
        renglones_grid = [(
            p["clave"], p["descripcion"], p["precio"], p["cantidad"],
            calcular_importe(p["precio"], p["cantidad"]),
        ) for p in self.carrito.values()]
        articulos = sum(r[3] for r in renglones_grid)

        exito, folio, datos_qr, num_compras, total_acumulado, promedio_ticket = \
            self.db.registrar_venta(config.EMPLEADO, renglones_grid, subtotal, iva, total)

        if not exito:
            error_sql = datos_qr
            if str(ER_CHECK_CONSTRAINT_VIOLATED) in error_sql or "chk_stock" in error_sql:
                detalle = "Stock insuficiente para completar la venta."
            else:
                detalle = f"Error de MySQL: {error_sql}"
            self._avisar_rollback(detalle)
            return

        fecha = datetime.now()
        self.ticket_confirmado = True
        self.carrito.clear()
        self.tabla.delete(*self.tabla.get_children())
        self.lbl_articulos.configure(text="0 artículos · 0 renglones")
        self.lbl_folio.configure(text=f"#{folio:05d}")
        self.lbl_subtotal.configure(text=moneda(subtotal))
        self.lbl_iva.configure(text=moneda(iva))
        self.lbl_total.configure(text=moneda(total))
        self._mostrar_qr(datos_qr)
        self._actualizar_ticket_preview(folio, fecha, total, articulos)

        self.kpi_total.configure(text=f"{moneda(total_acumulado)} MXN")
        self.kpi_promedio.configure(text=f"{moneda(promedio_ticket)} MXN / ticket")
        self.kpi_compras.configure(text=f"{num_compras} ticket{'s' if num_compras != 1 else ''}")
        self.folio_estimado = folio + 1

        messagebox.showinfo("Venta guardada",
                            f"Venta #{folio:05d} registrada correctamente.\n"
                            f"Total: {moneda(total)}")
        self._enfocar()

    def _avisar_rollback(self, detalle):
        for clave, p in self.carrito.items():
            try:
                prod = self.db.buscar_producto(clave)
                if prod:
                    p["stock"] = prod["stock"]
            except Error:
                break
        self._refrescar_grid()
        messagebox.showerror("Transacción revertida (ROLLBACK)",
                             f"{detalle}\n\nSe deshicieron los cambios en la base de datos.")
        self._actualizar_kpis()
        self._enfocar()

    def cancelar_venta(self, event=None):
        if not self.carrito:
            self._enfocar()
            return
        if messagebox.askyesno("Cancelar venta", "¿Deseas cancelar la venta actual?"):
            self.carrito.clear()
            self._refrescar_grid()
        self._enfocar()

    def destroy(self):
        self.db.cerrar()
        super().destroy()


if __name__ == "__main__":
    app = PuntoDeVentaApp()
    app.mainloop()
