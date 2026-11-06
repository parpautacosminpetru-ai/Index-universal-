"""Two independent offline preview panes; source is always the original local file."""
from __future__ import annotations

import io
from pathlib import Path
import tkinter as tk

try:
    import fitz
except ImportError:
    fitz = None
try:
    from PIL import Image, ImageTk
except ImportError:
    Image = ImageTk = None

BG = "#0f1b2d"
PANEL = "#17273b"
INK = "#eaf1fc"
MUTED = "#a4b9d2"
ACCENT = "#84d7e7"


class SourcePane(tk.Frame):
    def __init__(self, master, side):
        super().__init__(master,bg=BG,highlightbackground="#344459",highlightthickness=1)
        self.anchor=None
        self.doc=None
        self.current_page=0
        self.photo=None
        self.image_id=None
        self.side=side
        self.render_job=None
        self.source_path=None
        head=tk.Frame(self,bg=PANEL)
        head.pack(fill="x")
        tk.Label(head,text=f"ORIGINAL {side}",bg=PANEL,fg=ACCENT,font=("Segoe UI",10,"bold"),anchor="w").pack(side="left",padx=9,pady=8)
        self.page_info=tk.Label(head,text="",bg=PANEL,fg=MUTED,font=("Segoe UI",9))
        self.page_info.pack(side="right",padx=8)
        toolbar=tk.Frame(self,bg=BG)
        toolbar.pack(fill="x")
        for label,method in (("◀",self.previous),("▶",self.next_page),("−",self.zoom_out),("+",self.zoom_in)):
            tk.Button(toolbar,text=label,command=method,bg=PANEL,fg=INK,activebackground="#2c4d69",activeforeground="white",relief="flat",borderwidth=0,font=("Segoe UI",10,"bold"),padx=9,pady=3).pack(side="left",padx=(4,0),pady=5)
        self.title_label=tk.Label(self,bg=BG,fg=INK,anchor="w",justify="left",wraplength=350,font=("Segoe UI",9,"bold"),text="Selectează o trimitere către sursă.")
        self.title_label.pack(fill="x",padx=9,pady=(2,3))
        self.note_label=tk.Label(self,bg=BG,fg=MUTED,anchor="w",justify="left",wraplength=350,font=("Segoe UI",9),text="")
        self.note_label.pack(fill="x",padx=9,pady=(0,6))
        viewport=tk.Frame(self,bg="#d7dfe9")
        viewport.pack(fill="both",expand=True,padx=6,pady=(0,6))
        self.canvas=tk.Canvas(viewport,bg="#e9eef3",highlightthickness=0)
        self.scrollbar=tk.Scrollbar(viewport,orient="vertical",command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side="right",fill="y")
        self.canvas.pack(side="left",fill="both",expand=True)
        self.canvas.bind("<Configure>",self._resize)
        self.canvas.bind("<MouseWheel>",lambda e:self.canvas.yview_scroll(int(-e.delta/120),"units"))
        self.text=tk.Text(viewport,wrap="word",background="#f7f8fa",foreground="#26374b",font=("Georgia",11),padx=16,pady=16,relief="flat",state="disabled")
        self.zoom=1.0
        self.text_visible=False

    def _resize(self, _event=None):
        if self.anchor and self.source_path and self.source_path.suffix.lower()==".pdf":
            if self.render_job is not None:
                self.after_cancel(self.render_job)
            self.render_job=self.after(180,self.render)

    def _show_text(self, content, needle):
        if not self.text_visible:
            self.canvas.pack_forget()
            self.text.pack(side="left",fill="both",expand=True)
            self.scrollbar.configure(command=self.text.yview)
            self.text.configure(yscrollcommand=self.scrollbar.set)
            self.text_visible=True
        self.text.config(state="normal")
        self.text.delete("1.0","end")
        self.text.insert("1.0",content)
        self.text.tag_configure("match",background="#ffe991",foreground="#332400")
        if needle:
            pos=self.text.search(needle,"1.0",nocase=False)
            if pos:
                end=self.text.index(f"{pos}+{len(needle)}c")
                self.text.tag_add("match",pos,end)
                self.text.see(pos)
        self.text.config(state="disabled")

    def _show_canvas(self):
        if self.text_visible:
            self.text.pack_forget()
            self.canvas.pack(side="left",fill="both",expand=True)
            self.scrollbar.configure(command=self.canvas.yview)
            self.canvas.configure(yscrollcommand=self.scrollbar.set)
            self.text_visible=False

    def show(self, anchor):
        """anchor: mapping returned by get_anchor/evidence_for_relation."""
        self.anchor=dict(anchor)
        path=Path(anchor["file_path"])
        self.source_path=path
        self.title_label.config(text=anchor["source_title"])
        location=f"p. {anchor['page_first']}" if anchor["page_first"]==anchor["page_last"] else f"pp. {anchor['page_first']}–{anchor['page_last']}"
        other=[]
        if anchor["paragraph"]: other.append("paragraf "+anchor["paragraph"])
        if anchor["line"]: other.append("rând "+anchor["line"])
        self.note_label.config(text=location+(" · "+" · ".join(other) if other else ""))
        if self.doc is not None:
            self.doc.close();self.doc=None
        if not path.exists():
            self._show_canvas()
            self.canvas.delete("all")
            self.canvas.create_text(15,25,anchor="nw",text="Sursa nu mai este găsită la locația:\n"+str(path),fill="#7f2730",width=330,font=("Segoe UI",11))
            self.page_info.config(text="fișier lipsă")
            return
        if path.suffix.lower()==".txt":
            try:
                self._show_text(path.read_text(encoding="utf-8-sig"),anchor["exact_text"])
                self.page_info.config(text="TXT")
            except (OSError,UnicodeError) as exc:
                self._show_text("Eroare la deschiderea textului: "+str(exc),"")
            return
        if not fitz or not ImageTk:
            self._show_text("Pentru vizualizarea PDF-urilor trebuie instalate PyMuPDF și Pillow.","")
            return
        try:
            self.doc=fitz.open(str(path))
            self.current_page=min(max(0,anchor["page_first"]-1),max(len(self.doc)-1,0))
            self.zoom=1.0
            self._show_canvas()
            self.render()
        except Exception as exc:
            self._show_text("Eroare la deschiderea PDF-ului: "+str(exc),"")

    def render(self):
        self.render_job=None
        if not self.doc or not fitz or not ImageTk:
            return
        try:
            page=self.doc[self.current_page]
            available=max(self.canvas.winfo_width()-15,245)
            factor=min(2.6,max(0.3,available/page.rect.width*self.zoom))
            pix=page.get_pixmap(matrix=fitz.Matrix(factor,factor),alpha=False)
            img=Image.open(io.BytesIO(pix.tobytes("png")))
            self.photo=ImageTk.PhotoImage(img)
            self.canvas.delete("all")
            self.canvas.create_image(0,0,anchor="nw",image=self.photo)
            self.canvas.configure(scrollregion=(0,0,pix.width,pix.height))
            needle=(self.anchor or {}).get("exact_text","")
            if needle:
                try:
                    for r in page.search_for(needle):
                        self.canvas.create_rectangle(r.x0*factor,r.y0*factor,r.x1*factor,r.y1*factor,
                            fill="#ffe281",stipple="gray25",outline="#d79f17",width=2)
                except Exception:
                    pass
            self.page_info.config(text=f"p. {self.current_page+1} / {len(self.doc)}")
        except Exception as exc:
            self.canvas.delete("all")
            self.canvas.create_text(12,12,text=str(exc),fill="red",anchor="nw")

    def previous(self):
        if self.doc and self.current_page>0:
            self.current_page-=1;self.render()

    def next_page(self):
        if self.doc and self.current_page<len(self.doc)-1:
            self.current_page+=1;self.render()

    def zoom_in(self):
        if self.doc:
            self.zoom=min(3.0,self.zoom*1.2);self.render()

    def zoom_out(self):
        if self.doc:
            self.zoom=max(0.35,self.zoom/1.2);self.render()

    def shutdown(self):
        if self.doc:
            self.doc.close();self.doc=None
