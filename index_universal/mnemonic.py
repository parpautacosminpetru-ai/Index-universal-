"""Optional memory-loci board inspired by Hugo de Sancto Victore.

A numbered line folds into a visual grid (with a stable, per-board column count).
Slots are cues + references to existing canonical nodes, never copies of original sources.
This is a MEMORY view, not a mandatory conceptual taxonomy.
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import sqlite3

from .gui import BG, PANEL, CARD, FIELD, BORDER, WHITE, SECONDARY, ACCENT, label, button, Editor

PAGE_SIZE = 60


class MnemonicWindow(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app=app
        self.db=app.db
        self.title("Grilă mnemonică · număr, loc, timp")
        self.geometry("1120x800")
        self.minsize(730,500)
        self.configure(bg=BG)
        self.grid_id=None
        self.page=0
        self.selection=None
        self.protocol("WM_DELETE_WINDOW",self.shutdown)
        self.create_ui()
        grids=self.db.mnemonic_grids()
        if not grids:
            gid=self.db.mnemonic_grid("Grila universală",6)
            self.db.mnemonic_extend(gid,24)
        self.load_grids()

    def create_ui(self):
        top=tk.Frame(self,bg=PANEL)
        top.pack(fill="x")
        label(top,"MEMORIA · HUGO DE SAINT-VICTOR",14,True,bg=PANEL).pack(side="left",padx=16,pady=12)
        label(top,"numerus · locus · tempus",10,color=ACCENT,bg=PANEL).pack(side="right",padx=16)
        expl=tk.Frame(self,bg=BG)
        expl.pack(fill="x",padx=15,pady=(13,8))
        label(expl,"Poziții numerotate de memorare, fără ordine impusă informațiilor. "
              "Orice celulă trimite către o fișă deja existentă; memoria nu duplică originalul.",
              11,color=SECONDARY,wraplength=1000,justify="left").pack(anchor="w")
        toolbar=tk.Frame(self,bg=BG)
        toolbar.pack(fill="x",padx=15,pady=6)
        label(toolbar,"Grila",10,True).pack(side="left",padx=(0,7))
        self.choice=ttk.Combobox(toolbar,state="readonly",width=30)
        self.choice.pack(side="left",padx=(0,9))
        self.choice.bind("<<ComboboxSelected>>",lambda _ev:self.choose_grid())
        button(toolbar,"+ Grilă nouă",self.add_grid).pack(side="left",padx=3)
        button(toolbar,"+ 10 celule",lambda:self.add_cells(10)).pack(side="left",padx=3)
        button(toolbar,"+ 50 celule",lambda:self.add_cells(50)).pack(side="left",padx=3)
        pag=tk.Frame(self,bg=BG)
        pag.pack(fill="x",padx=15,pady=(5,7))
        self.position_label=label(pag,"",10,color=SECONDARY)
        self.position_label.pack(side="left")
        button(pag,"Următoarele →",lambda:self.move(1)).pack(side="right",padx=3)
        button(pag,"← Anterioarele",lambda:self.move(-1)).pack(side="right",padx=3)
        holder=tk.Frame(self,bg=BG)
        holder.pack(fill="both",expand=True,padx=12,pady=(0,10))
        self.canvas=tk.Canvas(holder,bg=BG,highlightthickness=0)
        bar=tk.Scrollbar(holder,orient="vertical",command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=bar.set)
        bar.pack(side="right",fill="y")
        self.canvas.pack(side="left",fill="both",expand=True)
        self.board=tk.Frame(self.canvas,bg=BG)
        win=self.canvas.create_window((0,0),window=self.board,anchor="nw")
        self.board.bind("<Configure>",lambda _ev:self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>",lambda ev:self.canvas.itemconfigure(win,width=ev.width-4))
        self.canvas.bind("<MouseWheel>",lambda e:self.canvas.yview_scroll(int(-e.delta/120),"units"))
        label(self,"Aceasta este o suprapunere mnemonică facultativă. "
              "Indiciile de memorare nu reprezintă fapte atribuite surselor.",
              10,color=SECONDARY).pack(padx=15,pady=(0,12),anchor="w")

    def load_grids(self,select_id=None):
        gs=self.db.mnemonic_grids()
        self.grid_choices={g["title"]:g["id"] for g in gs}
        self.choice["values"]=list(self.grid_choices)
        desired=next((g["title"] for g in gs if g["id"]==select_id),None)
        if not desired:
            desired=next((g["title"] for g in gs if g["id"]==self.grid_id),None)
        self.choice.set(desired or (gs[0]["title"] if gs else ""))
        self.choose_grid()

    def choose_grid(self):
        self.grid_id=self.grid_choices.get(self.choice.get())
        self.page=0
        self.render()

    def add_grid(self):
        title=simpledialog.askstring("Grilă nouă","Numele grilei (nu este o categorie a cunoașterii):",parent=self)
        if title is None:return
        columns=simpledialog.askinteger("Poziții stabile","Câte coloane vizuale? (2–12) "
                       "Păstrăm această dispunere pentru memorie.",initialvalue=6,minvalue=2,maxvalue=12,parent=self)
        if columns is None:return
        try:
            gid=self.db.mnemonic_grid(title,columns)
            if self.db.mnemonic_cell_count(gid)==0:self.db.mnemonic_extend(gid,columns*4)
            self.load_grids(gid)
        except (ValueError,sqlite3.Error) as exc:
            messagebox.showerror("Grila nu a fost creată",str(exc),parent=self)

    def add_cells(self,n):
        if not self.grid_id:return
        try:
            last=self.db.mnemonic_extend(self.grid_id,n)
            self.page=(last-1)//PAGE_SIZE
            self.render()
        except (ValueError,sqlite3.Error) as exc:
            messagebox.showerror("Celule",str(exc),parent=self)

    def move(self,direction):
        count=self.db.mnemonic_cell_count(self.grid_id)
        pages=max(1,(count+PAGE_SIZE-1)//PAGE_SIZE)
        self.page=max(0,min(pages-1,self.page+direction))
        self.render()

    def jump_to(self,grid_id,position=None):
        self.load_grids(grid_id)
        if position:
            self.page=(int(position)-1)//PAGE_SIZE
            self.selection=int(position)
            self.render()
        self.lift()

    def render(self):
        for child in self.board.winfo_children():child.destroy()
        if not self.grid_id:return
        g=self.db.mnemonic_grid_by_id(self.grid_id)
        count=self.db.mnemonic_cell_count(self.grid_id)
        pages=max(1,(count+PAGE_SIZE-1)//PAGE_SIZE)
        self.page=min(max(self.page,0),pages-1)
        rows=self.db.mnemonic_cells(self.grid_id,self.page*PAGE_SIZE,PAGE_SIZE)
        self.position_label.configure(text=f"Locuri de memorie: {count} · "
                    f"pagina {self.page+1}/{pages} · {g['columns']} coloane stabile")
        cols=int(g["columns"])
        for col in range(cols):self.board.grid_columnconfigure(col,weight=1,uniform="mnemonic")
        for ix,cell in enumerate(rows):
            r,c=divmod(ix,cols)
            tile=tk.Frame(self.board,bg=CARD,highlightbackground=ACCENT if cell["position"]==self.selection else BORDER,
                          highlightthickness=2 if cell["position"]==self.selection else 1)
            tile.grid(row=r,column=c,sticky="nsew",padx=4,pady=4)
            top=tk.Frame(tile,bg=CARD)
            top.pack(fill="x",padx=7,pady=(7,2))
            label(top,"LOC "+str(cell["position"]),9,True,color=ACCENT,bg=CARD).pack(side="left")
            button(top,"✎",lambda p=cell["position"]:self.edit_cell(p)).pack(side="right")
            title=cell["node_title"] or "+ Alege fișa"
            if cell["node_title"]:
                button(tile,title,lambda n=cell["node_title"]:self.open_node(n),True,
                      wraplength=140).pack(fill="x",padx=6,pady=5)
            else:
                button(tile,title,lambda p=cell["position"]:self.edit_cell(p),
                      wraplength=140).pack(fill="x",padx=6,pady=5)
            notes=[]
            if cell["cue"]:notes.append("Imagine: "+cell["cue"])
            if cell["place_cue"]:notes.append("Loc: "+cell["place_cue"])
            if cell["time_cue"]:notes.append("Timp: "+cell["time_cue"])
            label(tile,"\n".join(notes) if notes else "Loc liber de memorare",
                  9,color=SECONDARY,bg=CARD,wraplength=155,justify="left").pack(
                   anchor="w",fill="x",padx=7,pady=(3,10))
        self.canvas.yview_moveto(0)

    def edit_cell(self,position):
        cell=self.db.mnemonic_cell(self.grid_id,position)
        d=Editor(self.app,f"Loc mnemonic {position}",600)
        d.geometry("600x620")
        opts=["(loc fără fișă)"]+[n["title"] for n in self.db.nodes()]
        d.selector("Fișă existentă — trimitere unică",opts,
                   cell["node_title"] or opts[0])
        d.field("Imagine / cuvânt de reamintire (nu este citat)",cell["cue"],multiline=True)
        d.field("Locus mental / reper spațial",cell["place_cue"],multiline=True)
        d.field("Reper temporal mnemonic",cell["time_cue"],multiline=True)
        label(d.form,"Poziția rămâne stabilă. Fișa și sursele sunt păstrate numai în indexul original.",
              9,color=ACCENT,wraplength=540,justify="left").pack(anchor="w",pady=(8,0))
        def save():
            selected=d.value("Fișă existentă — trimitere unică")
            self.db.mnemonic_assign(self.grid_id,position,
                selected if selected!=opts[0] else None,
                d.value("Imagine / cuvânt de reamintire (nu este citat)"),
                d.value("Locus mental / reper spațial"),
                d.value("Reper temporal mnemonic"))
            self.selection=position
            self.render()
        d.commit_button("Salvează poziția mnemonică",save)

    def open_node(self,title):
        self.app.focus(title)
        self.app.lift()

    def shutdown(self):
        self.app.mnemonic_window=None
        self.destroy()
