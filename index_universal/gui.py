"""Windows desktop: one search, contextual source buttons, two original-source panes."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from pathlib import Path
import sqlite3

from .db import IndexDB, join_location
from .pdfpane import SourcePane

BG="#0b1422"
PANEL="#142238"
CARD="#1c2d43"
FIELD="#22344a"
WHITE="#ecf4ff"
SECONDARY="#a4bad3"
ACCENT="#83d7e8"
BORDER="#314861"
YELLOW="#ffdb81"


def label(parent, text, size=10, bold=False, color=WHITE, bg=None, **kwargs):
    return tk.Label(parent,text=text,font=("Segoe UI",size,"bold" if bold else "normal"),
                    bg=bg or parent.cget("bg"),fg=color,**kwargs)


def button(parent, text, callback, accent=False, **kwargs):
    return tk.Button(parent,text=text,command=callback,font=("Segoe UI",10,"bold" if accent else "normal"),
                     bg=ACCENT if accent else FIELD,fg="#062233" if accent else WHITE,
                     activebackground="#c7f5ff" if accent else "#355371",
                     activeforeground="#062233" if accent else WHITE,
                     relief="flat",cursor="hand2",padx=11,pady=7,bd=0,**kwargs)


class Editor(tk.Toplevel):
    def __init__(self, app, title, width=660):
        super().__init__(app)
        self.app=app
        self.title(title)
        self.configure(bg=BG)
        self.geometry(f"{width}x780")
        self.minsize(500,540)
        self.transient(app)
        self.grab_set()
        label(self,title,17,True).pack(fill="x",padx=20,pady=(14,8))
        holder=tk.Frame(self,bg=BG)
        holder.pack(fill="both",expand=True,padx=12,pady=(0,10))
        canvas=tk.Canvas(holder,bg=BG,highlightthickness=0)
        bar=tk.Scrollbar(holder,orient="vertical",command=canvas.yview)
        canvas.configure(yscrollcommand=bar.set)
        bar.pack(side="right",fill="y")
        canvas.pack(side="left",fill="both",expand=True)
        container=tk.Frame(canvas,bg=BG)
        window=canvas.create_window((0,0),window=container,anchor="nw")
        container.bind("<Configure>",lambda _:canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",lambda ev:canvas.itemconfigure(window,width=ev.width-6))
        self.form=container
        self.fields={}

    def field(self, name, value="", multiline=False):
        label(self.form,name,10,True,color=SECONDARY).pack(fill="x",pady=(8,3))
        if multiline:
            widget=tk.Text(self.form,height=4,wrap="word",font=("Segoe UI",10),bg=FIELD,fg=WHITE,
                           insertbackground=WHITE,relief="flat",highlightthickness=1,highlightbackground=BORDER)
            widget.insert("1.0",str(value))
        else:
            widget=tk.Entry(self.form,font=("Segoe UI",11),bg=FIELD,fg=WHITE,insertbackground=WHITE,
                            relief="flat",highlightthickness=1,highlightbackground=BORDER)
            widget.insert(0,str(value))
        widget.pack(fill="x",ipady=7 if not multiline else 0)
        self.fields[name]=widget
        return widget

    def value(self,name):
        w=self.fields[name]
        return (w.get("1.0","end-1c") if isinstance(w,tk.Text) else w.get()).strip()

    def selector(self,name,values,initial=None):
        label(self.form,name,10,True,color=SECONDARY).pack(fill="x",pady=(8,3))
        w=ttk.Combobox(self.form,values=values,state="readonly",font=("Segoe UI",10))
        w.pack(fill="x",ipady=3)
        if initial in values:w.set(initial)
        elif values:w.current(0)
        self.fields[name]=w
        return w

    def commit_button(self,title,fn):
        def run():
            try:
                fn()
            except (ValueError,sqlite3.Error,OSError) as exc:
                messagebox.showerror("Nu s-a salvat",str(exc),parent=self)
            else:
                self.app.do_search()
                self.app.update_stats()
                self.destroy()
        b=button(self.form,title,run,True)
        b.pack(fill="x",pady=(16,6))


class IndexUniversal(tk.Tk):
    def __init__(self, data_dir):
        super().__init__()
        self.db=IndexDB(data_dir)
        self.title("Index Universal — bibliotecă relațională offline")
        self.geometry("1510x900")
        self.minsize(1120,670)
        self.configure(bg=BG)
        self.search_delay=None
        self.loaded=0
        self.current_query=""
        self.selected_node=None
        self.mnemonic_window=None
        self.make_ui()
        self.protocol("WM_DELETE_WINDOW",self.shutdown)
        self.update_stats()
        self.do_search()
        self.after(150,self.search_entry.focus_set)

    def make_ui(self):
        header=tk.Frame(self,bg=PANEL)
        header.pack(fill="x")
        label(header,"INDEX UNIVERSAL",18,True,color=WHITE,bg=PANEL).pack(side="left",padx=(17,8),pady=13)
        label(header,"Fișe · relații în oglindă · surse originale",10,color=SECONDARY,bg=PANEL).pack(side="left",pady=14)
        label(header,"●  OFFLINE",10,True,color="#8ae3bd",bg=PANEL).pack(side="right",padx=17)

        tool=tk.Frame(self,bg=BG)
        tool.pack(fill="x",padx=14,pady=(10,6))
        for text,action in (("+ Informație",self.add_node),("+ Relație",self.add_relation),
                            ("+ Surse PDF / TXT",self.import_sources),("Catalog surse",self.catalog_sources),("+ Ancorează fișă",self.anchor_node),
                            ("Grilă mnemonică",self.open_mnemonic),
                            ("Salvează arhivă",self.export_archive),("Restaurează",self.restore_archive)):
            button(tool,text,action).pack(side="left",padx=(0,6))

        search=tk.Frame(self,bg=BG)
        search.pack(fill="x",padx=16,pady=(2,9))
        label(search,"Caută",11,True).pack(side="left",padx=(0,13))
        self.search_var=tk.StringVar()
        self.search_entry=tk.Entry(search,textvariable=self.search_var,font=("Segoe UI",17),
                                   bg=FIELD,fg=WHITE,insertbackground=WHITE,relief="flat",
                                   highlightthickness=1,highlightbackground="#55748a")
        self.search_entry.pack(side="left",fill="x",expand=True,ipady=8)
        self.search_entry.bind("<KeyRelease>",self.schedule_search)
        self.search_entry.bind("<Return>",lambda _:self.do_search())
        button(search,"Caută",self.do_search,True).pack(side="left",padx=(8,0))

        split=tk.PanedWindow(self,orient="horizontal",sashwidth=7,bg=BG,bd=0,relief="flat")
        split.pack(fill="both",expand=True,padx=12,pady=(0,10))
        left=tk.Frame(split,bg=BG)
        right=tk.Frame(split,bg=BG)
        split.add(left,minsize=430,width=690)
        split.add(right,minsize=500)

        header_l=tk.Frame(left,bg=BG)
        header_l.pack(fill="x",pady=(5,8))
        label(header_l,"TRIMITERI CONTEXTUALIZATE",11,True,color=ACCENT).pack(side="left",padx=3)
        self.count_label=label(header_l,"",9,color=SECONDARY)
        self.count_label.pack(side="right",padx=6)
        self.scroll=tk.Canvas(left,highlightthickness=0,bg=BG)
        s=tk.Scrollbar(left,orient="vertical",command=self.scroll.yview)
        self.scroll.configure(yscrollcommand=s.set)
        s.pack(side="right",fill="y")
        self.scroll.pack(side="left",fill="both",expand=True)
        self.cards=tk.Frame(self.scroll,bg=BG)
        self.cards_window=self.scroll.create_window((0,0),window=self.cards,anchor="nw")
        self.cards.bind("<Configure>",lambda _:self.scroll.configure(scrollregion=self.scroll.bbox("all")))
        self.scroll.bind("<Configure>",lambda event:self.scroll.itemconfigure(self.cards_window,width=max(280,event.width)))
        self.scroll.bind("<MouseWheel>",lambda e:self.scroll.yview_scroll(int(-e.delta/120),"units"))
        self.cards.bind("<MouseWheel>",lambda e:self.scroll.yview_scroll(int(-e.delta/120),"units"))

        right_head=tk.Frame(right,bg=BG)
        right_head.pack(fill="x",pady=(5,8))
        label(right_head,"PASAJ ORIGINAL · DOUĂ SURSE ÎN PARALEL",11,True,color=ACCENT).pack(side="left",padx=5)
        panes=tk.PanedWindow(right,orient="horizontal",sashwidth=5,bg=BG,bd=0)
        panes.pack(fill="both",expand=True)
        self.preview_a=SourcePane(panes,"A")
        self.preview_b=SourcePane(panes,"B")
        panes.add(self.preview_a,minsize=220)
        panes.add(self.preview_b,minsize=220)
        bottom=tk.Frame(self,bg=PANEL)
        bottom.pack(fill="x")
        self.stats_label=label(bottom,"",9,color=SECONDARY,bg=PANEL)
        self.stats_label.pack(side="left",padx=15,pady=8)
        label(bottom,"Apare numai ce ai indexat. Nicio inferență automată.",9,color="#8ae3bd",bg=PANEL).pack(side="right",padx=14)

    def update_stats(self):
        s=self.db.stats()
        self.stats_label.config(text=f"{s['nodes']} fișe · {s['relations']} relații unice · {s['sources']} surse · {s['anchors']} ancore")

    def schedule_search(self,_event=None):
        if self.search_delay:
            self.after_cancel(self.search_delay)
        self.search_delay=self.after(230,self.do_search)

    def focus(self,title):
        self.search_var.set(title)
        self.do_search()

    def clear_cards(self):
        for ch in self.cards.winfo_children():ch.destroy()
        self.scroll.yview_moveto(0)

    def do_search(self):
        if self.search_delay:
            self.after_cancel(self.search_delay);self.search_delay=None
        query=self.search_var.get().strip()
        self.current_query=query
        self.loaded=0
        self.clear_cards()
        self.selected_node=self.db.get_node(query)
        if not query:
            label(self.cards,"Scrie orice informație sau combinație de termeni.",13,True,
                  color=WHITE,wraplength=550,justify="left").pack(anchor="w",padx=12,pady=(30,12))
            label(self.cards,"Tot ceea ce apare aici provine exclusiv din ceea ce ai indexat. "
                  "Relațiile apar în ambele sensuri, fără copii și fără presupuneri.",
                  11,color=SECONDARY,wraplength=550,justify="left").pack(anchor="w",padx=12)
            self.count_label.config(text="Bază locală")
            return
        total=self.db.count_matches(query)
        self.count_label.config(text=f"{total} relații indexate")
        if self.selected_node:
            self.render_selected_node(self.selected_node)
        else:
            possibles=self.db.find_nodes(query,limit=10)
            if possibles:
                box=tk.Frame(self.cards,bg=BG)
                box.pack(fill="x",padx=7,pady=(3,8))
                label(box,"FIȘE CARE CORESPUND CĂUTĂRII",9,True,color=SECONDARY).pack(anchor="w")
                row=tk.Frame(box,bg=BG)
                row.pack(fill="x",pady=4)
                for n in possibles[:5]:
                    button(row,n["title"],lambda title=n["title"]:self.focus(title)).pack(side="left",padx=(0,5),pady=2)
        self.load_more()

    def render_selected_node(self,node):
        head=tk.Frame(self.cards,bg=PANEL,highlightbackground=BORDER,highlightthickness=1)
        head.pack(fill="x",padx=7,pady=(4,11))
        label(head,node["title"],19,True,bg=PANEL).pack(anchor="w",padx=12,pady=(10,4))
        if node["descriptor"]:
            label(head,node["descriptor"],10,color=SECONDARY,bg=PANEL,wraplength=580,justify="left").pack(anchor="w",padx=12,pady=(0,7))
        actions=tk.Frame(head,bg=PANEL)
        actions.pack(fill="x",padx=10,pady=(2,8))
        button(actions,"+ Relație din această fișă",lambda:self.add_relation(prefill=node["title"])).pack(side="left",padx=(0,6))
        button(actions,"Redenumește",lambda:self.rename_node(node)).pack(side="left")
        direct=self.db.evidence_for_node(node["id"])
        if direct:
            label(head,"Ancore proprii în surse:",9,True,bg=PANEL,color=ACCENT).pack(anchor="w",padx=12,pady=(0,3))
            for a in direct:
                r=tk.Frame(head,bg=PANEL)
                r.pack(fill="x",padx=12,pady=2)
                label(r,a["source_title"]+" · "+join_location(a),9,color=SECONDARY,bg=PANEL).pack(side="left")
                button(r,"Original A",lambda item=dict(a):self.preview_a.show(item)).pack(side="right",padx=2)
                button(r,"Original B",lambda item=dict(a):self.preview_b.show(item)).pack(side="right",padx=2)

        self.mnemonic_links(node,head)

    def mnemonic_links(self,node,head):
        loci=self.db.mnemonic_places_for_node(node["id"])
        if not loci:
            return
        label(head,"Locuri mnemonice (trimiteri, nu copii):",9,True,
              bg=PANEL,color=ACCENT).pack(anchor="w",padx=12,pady=(7,3))
        line=tk.Frame(head,bg=PANEL)
        line.pack(fill="x",padx=12,pady=(0,6))
        for loc in loci[:8]:
            button(line,loc["grid_title"]+" · poziția "+str(loc["position"]),
                   lambda g=loc["grid_id"],p=loc["position"]:self.open_mnemonic(g,p)).pack(side="left",padx=2)
        if len(loci)>8:
            label(head,f"+ {len(loci)-8} alte locuri mnemonice",9,
                  color=SECONDARY,bg=PANEL).pack(anchor="w",padx=12,pady=2)

    def load_more(self):
        q=self.current_query
        if not q:return
        rows=self.db.matches(q,limit=40,offset=self.loaded)
        if self.loaded==0 and not rows and not self.selected_node:
            label(self.cards,"Nu există trimiteri pentru această căutare în indexul tău.",11,color=SECONDARY,
                  wraplength=580).pack(anchor="w",padx=12,pady=20)
        for r in rows:self.render_relation(r)
        self.loaded+=len(rows)
        total=self.db.count_matches(q)
        if self.loaded<total:
            button(self.cards,f"Mai multe trimiteri ({total-self.loaded} rămase)",self.load_more,True).pack(fill="x",padx=9,pady=13)
        # Old 'Mai multe' controls must not accumulate when moving to next page.
        for ch in list(self.cards.winfo_children()):
            if isinstance(ch,tk.Button) and ch.cget("text").startswith("Mai multe") and ch is not self.cards.winfo_children()[-1]:
                ch.destroy()

    def render_relation(self,r):
        block=tk.Frame(self.cards,bg=CARD,highlightbackground=BORDER,highlightthickness=1)
        block.pack(fill="x",padx=7,pady=5)
        oriented = self.selected_node and r["object_id"]==self.selected_node["id"]
        other=r["subject"] if oriented else r["object"]
        if self.selected_node:
            title=other
        else:
            title=r["subject"]+"   →   "+r["object"]
        label(block,title,13,True,bg=CARD,wraplength=595,justify="left").pack(anchor="w",padx=11,pady=(9,2))
        relation_text=f"{r['subject']}  — {r['predicate']} →  {r['object']}"
        label(block,relation_text,10,color=ACCENT,bg=CARD,wraplength=595,justify="left").pack(anchor="w",padx=11)
        if r["context"]:
            label(block,"Context: "+r["context"],10,color=WHITE,bg=CARD,wraplength=595,justify="left").pack(anchor="w",padx=11,pady=(4,0))
        q=self.db.qualities(r["id"])
        if q:
            s="   ·   ".join(f"{x['criterion']}: {x['value']}" for x in q)
            label(block,s,10,color=YELLOW,bg=CARD,wraplength=595,justify="left").pack(anchor="w",padx=11,pady=(4,0))
        label(block,"Statut: "+r["status"],9,color=SECONDARY,bg=CARD).pack(anchor="w",padx=11,pady=(3,2))
        evid=self.db.evidence_for_relation(r["id"])
        for a in evid:
            row=tk.Frame(block,bg="#233951")
            row.pack(fill="x",padx=9,pady=3)
            label(row,"↳ "+a["source_title"]+" · "+join_location(a),9,bg="#233951",
                  color=WHITE,wraplength=360,justify="left").pack(side="left",fill="x",expand=True,padx=6,pady=5)
            button(row,"A",lambda item=dict(a):self.preview_a.show(item),accent=True).pack(side="right",padx=(3,4))
            button(row,"B",lambda item=dict(a):self.preview_b.show(item),accent=True).pack(side="right",padx=(3,1))
        if not evid:
            label(block,"Sursă neancorată — de verificat direct în original.",9,color="#e8b7a4",bg=CARD).pack(anchor="w",padx=11,pady=4)
        footer=tk.Frame(block,bg=CARD)
        footer.pack(fill="x",padx=9,pady=(3,8))
        if self.selected_node:
            button(footer,"Deschide fișa: "+other,lambda name=other:self.focus(name)).pack(side="left",padx=(0,6))
        else:
            button(footer,"Fișa: "+r["subject"],lambda n=r["subject"]:self.focus(n)).pack(side="left",padx=(0,5))
            button(footer,"Fișa: "+r["object"],lambda n=r["object"]:self.focus(n)).pack(side="left",padx=(0,5))
        button(footer,"Modifică relația",lambda rid=r["id"]:self.add_relation(edit_id=rid)).pack(side="right")

    def add_node(self):
        d=Editor(self,"Informație nouă",570)
        d.geometry("570x360")
        d.field("Denumire unică")
        d.field("Precizare pentru diferențiere (opțional)",multiline=True)
        def save():
            name=d.value("Denumire unică")
            self.db.node(name,d.value("Precizare pentru diferențiere (opțional)"))
            self.search_var.set(name)
        d.commit_button("Salvează fișa",save)

    def rename_node(self,node):
        d=Editor(self,"Modifică denumirea fișei",570)
        d.geometry("570x360")
        d.field("Denumire",node["title"])
        d.field("Precizare",node["descriptor"],multiline=True)
        def save():
            name=d.value("Denumire")
            self.db.rename_node(node["id"],name,d.value("Precizare"))
            self.search_var.set(name)
        d.commit_button("Salvează corectura",save)

    def imported_source_choices(self):
        return {f"{s['title']}  —  {s['file_path']}":s["id"] for s in self.db.sources()}

    def add_relation(self,prefill="",edit_id=None):
        old=self.db.relation_by_id(edit_id) if edit_id else None
        d=Editor(self,"Modifică relația" if old else "Relație contextualizată nouă",710)
        if old:d.geometry("710x850")
        d.field("Informația de plecare",old["subject"] if old else prefill)
        d.field("Relația exactă (în cuvinte)",old["predicate"] if old else "")
        d.field("Informația de destinație",old["object"] if old else "")
        d.field("Contextul explicit / precizări",old["context"] if old else "",multiline=True)
        qualities="\n".join(f"{x['criterion']}: {x['value']}" for x in self.db.qualities(edit_id)) if old else ""
        d.field("Criterii nelimitate, unul pe rând: criteriu: valoare",qualities,multiline=True)
        d.selector("Statut separat",["explicit","interpretare","inferență","de verificat"],old["status"] if old else "explicit")
        choices=self.imported_source_choices()
        d.selector("Ancoră de sursă (opțional)",["Fără sursă"]+list(choices),"Fără sursă")
        d.field("Pagina de început", "1")
        d.field("Pagina de sfârșit (opțional)")
        d.field("Paragraf (opțional)")
        d.field("Rând (opțional)")
        d.field("Fragment exact pentru evidențiere în PDF (opțional)")
        label(d.form,"Relația este salvată o singură dată și accesibilă din ambele fișe.",9,color=ACCENT).pack(anchor="w",pady=(10,0))
        def save():
            criteria=[]
            for line in d.value("Criterii nelimitate, unul pe rând: criteriu: valoare").splitlines():
                if line.strip():
                    if ":" not in line:raise ValueError("Fiecare criteriu trebuie introdus ca «criteriu: valoare».")
                    k,v=line.split(":",1)
                    if not k.strip() or not v.strip():raise ValueError("Criteriul și valoarea nu pot fi goale.")
                    criteria.append((k.strip(),v.strip()))
            status=d.value("Statut separat")
            if old:
                self.db.update_relation(edit_id,d.value("Informația de plecare"),d.value("Relația exactă (în cuvinte)"),
                                        d.value("Informația de destinație"),d.value("Contextul explicit / precizări"),
                                        status,criteria)
                rid=edit_id
            else:
                rid=self.db.relation(d.value("Informația de plecare"),d.value("Relația exactă (în cuvinte)"),
                                     d.value("Informația de destinație"),d.value("Contextul explicit / precizări"),
                                     status,criteria)
            source=d.value("Ancoră de sursă (opțional)")
            if source!="Fără sursă":
                aid=self.db.anchor(choices[source],d.value("Pagina de început"),
                                   d.value("Pagina de sfârșit (opțional)") or None,
                                   d.value("Paragraf (opțional)"),d.value("Rând (opțional)"),
                                   d.value("Fragment exact pentru evidențiere în PDF (opțional)"))
                self.db.attach_relation(rid,aid)
            self.search_var.set(d.value("Informația de plecare"))
        d.commit_button("Salvează relația și trimiterile în oglindă",save)

    def import_sources(self):
        paths=filedialog.askopenfilenames(title="Selectează surse originale (PDF sau TXT)",
                                          filetypes=[("Surse originale","*.pdf *.txt"),("PDF","*.pdf"),("Text","*.txt")])
        if not paths:return
        copied=messagebox.askyesno("Bibliotecă offline","Să păstrăm câte o copie a fișierelor în biblioteca aplicației?\n\nDa = surse administrate local.\nNu = referințe la fișierele existente.",parent=self)
        n=0
        for path in paths:
            try:
                self.db.source(path,copy_in=copied)
                n+=1
            except (ValueError,OSError) as exc:
                messagebox.showwarning("Sursă omisă",f"{path}\n{exc}",parent=self)
        self.update_stats()
        messagebox.showinfo("Surse înregistrate",f"{n} surse adăugate/recunoscute.\nDocumentele nu sunt transcrise sau indexate automat.",parent=self)

    def catalog_sources(self):
        sources=self.db.sources()
        if not sources:
            messagebox.showinfo("Catalog", "Nu există surse. Importă mai întâi PDF-uri sau TXT-uri.",parent=self)
            return
        d=Editor(self,"Catalogul surselor — metadate bibliografice",680)
        d.geometry("680x720")
        options={f"{s['title']} — {s['file_path']}":s for s in sources}
        choose=d.selector("Sursa de editat",list(options))
        title=d.field("Titlul sursei")
        creator=d.field("Autor / editor")
        edition=d.field("Ediție, an, identificare bibliografică",multiline=True)
        def populate(_event=None):
            row=options.get(choose.get())
            if not row:return
            for widget,key in [(title,"title"),(creator,"creator")]:
                widget.delete(0,"end");widget.insert(0,row[key])
            edition.delete("1.0","end");edition.insert("1.0",row["edition"])
        choose.bind("<<ComboboxSelected>>",populate)
        populate()
        def save():
            s=options[choose.get()]
            self.db.update_source(s["id"],d.value("Titlul sursei"),d.value("Autor / editor"),
                                  d.value("Ediție, an, identificare bibliografică"))
        d.commit_button("Salvează metadatele sursei",save)

    def anchor_node(self):
        names=[n["title"] for n in self.db.nodes()]
        sources=self.imported_source_choices()
        if not names:
            messagebox.showinfo("Fișe", "Creează mai întâi o fișă.",parent=self);return
        if not sources:
            messagebox.showinfo("Surse", "Importă mai întâi un PDF sau TXT.",parent=self);return
        d=Editor(self,"Ancorează fișa în sursa originală",630)
        selected=self.selected_node["title"] if self.selected_node else names[0]
        d.selector("Informație",names,selected)
        d.selector("Sursă",list(sources))
        d.field("Pagina de început","1")
        d.field("Pagina de sfârșit (opțional)")
        d.field("Paragraf (opțional)")
        d.field("Rând (opțional)")
        d.field("Fragment exact pentru evidențiere (opțional)")
        def save():
            src=sources[d.value("Sursă")]
            aid=self.db.anchor(src,d.value("Pagina de început"),d.value("Pagina de sfârșit (opțional)") or None,
                               d.value("Paragraf (opțional)"),d.value("Rând (opțional)"),
                               d.value("Fragment exact pentru evidențiere (opțional)"))
            n=self.db.get_node(d.value("Informație"))
            self.db.attach_node(n["id"],aid)
            self.search_var.set(n["title"])
        d.commit_button("Salvează ancora exactă",save)

    def open_mnemonic(self, grid_id=None, position=None):
        from .mnemonic import MnemonicWindow
        if self.mnemonic_window and self.mnemonic_window.winfo_exists():
            self.mnemonic_window.lift()
            self.mnemonic_window.focus_set()
            if grid_id is not None:
                self.mnemonic_window.jump_to(grid_id,position)
        else:
            self.mnemonic_window=MnemonicWindow(self)
            if grid_id is not None:
                self.mnemonic_window.jump_to(grid_id,position)

    def export_archive(self):
        path=filedialog.asksaveasfilename(title="Arhivă completă offline",defaultextension=".zip",
                  initialfile="Index-Universal-backup.zip",filetypes=[("Arhivă ZIP","*.zip")])
        if not path:return
        try:
            self.db.export_zip(path)
            messagebox.showinfo("Arhivă salvată",f"Baza și sursele disponibile au fost arhivate în:\n{path}",parent=self)
        except (OSError,sqlite3.Error,ValueError) as exc:
            messagebox.showerror("Export eșuat",str(exc),parent=self)

    def restore_archive(self):
        path=filedialog.askopenfilename(title="Restaurează copia Index Universal",filetypes=[("Arhivă ZIP","*.zip")])
        if not path:return
        if not messagebox.askyesno("Atenție — restaurare","Datele curente vor fi înlocuite cu cele din arhivă.\nO copie de siguranță a bazei actuale va fi păstrată. Continui?",parent=self):return
        try:
            self.preview_a.shutdown();self.preview_b.shutdown()
            self.db.restore_zip(path)
            self.search_var.set("")
            self.do_search();self.update_stats()
            messagebox.showinfo("Restaurare completă","Arhiva a fost restaurată. Sursa și trimiterile au fost păstrate.",parent=self)
        except Exception as exc:
            messagebox.showerror("Restaurare eșuată",str(exc),parent=self)

    def shutdown(self):
        self.preview_a.shutdown();self.preview_b.shutdown()
        self.db.close()
        self.destroy()
