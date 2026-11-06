# Index Universal — Windows, offline

**Versiunea 0.2 — prototip funcțional desktop, cu grilă mnemonică extensibilă.** O aplicație Windows separată de History-lab, concepută pentru o bibliotecă personală sau un proiect de cercetare în care **fiecare informație se înregistrează o singură dată** și poate fi regăsită prin toate relațiile documentate.

Nu există fișe demonstrative preîncărcate. Baza pornește goală. Nu există interpretare automată, internet obligatoriu sau categorii conceptuale impuse.

## Cum arată

- **Sus:** o singură bară în care scrii „Europa”, „Clovis” sau mai mulți termeni simultan.
- **Stânga:** toate relațiile *indexate* care corespund întrebării, fiecare cu contextul ei, criterii și dovezi. Fișele și relațiile sunt accesibile prin butoane.
- **Dreapta:** **două vizualizatoare pentru sursele originale**, în paralel. Butoanele **A** și **B** deschid direct pagina originală în panoul dorit, fără să elimine lista de rezultate.
- **Click pe numele fișei:** acea informație devine noul centru al căutării. Nu există ierarhie fixă sau hartă obligatorie.

## Funcționalități implementate

1. **O fișă unică per denumire**, fără coduri vizibile utilizatorului (identificatorii tehnici există numai în SQLite).
2. **Relație unică, cu acces în ambele sensuri**, generat automat. De exemplu, `Clovis I — a activat în → Europa` apare la căutarea „Clovis I” **și** la căutarea „Europa”, fără a doua înregistrare. Sensul nu se inversează semantic în mod fals.
3. **Criterii libere, nelimitate ca tip**, înregistrate ca perechi `criteriu: valoare` pe fiecare relație.
4. **Contextul relației și statutul epistemic** sunt înregistrate separat: `explicit`, `interpretare`, `inferență`, `de verificat`.
5. **Surse originale PDF/TXT**: import unul sau mai multe fișiere, cu opțiune de copiere în biblioteca locală sau păstrare la locul original. Fișierele identice sunt deduplicate la importul administrat local.
6. **Proveniență manuală precisă**: pagină, interval de pagini, paragraf, rând, fragment-locator exact. O singură ancoră poate justifica oricâte fișe și relații; aceeași relație poate avea oricâte surse.
7. **Vizualizare PDF locală**, cu evidențierea fragmentului-locator atunci când textul poate fi găsit pe pagină. Paginile scanate fără strat de text se pot vizualiza, dar selecția textului necesită OCR separat.
8. **Căutare full-text în indexul creat manual**, cu mai mulți termeni combinați prin AND. Caută în denumiri, predicate, contexte, criterii, autori, ediții, surse și fragmentele-locator înregistrate.
9. **Redenumirea fișelor și modificarea relațiilor** nu rup conexiunile. Metadatele bibliografice ale surselor pot fi corectate.
10. **Arhivă ZIP completă și restaurare**, cu bază de date SQLite și sursele disponibile.
11. **Grilă mnemonică facultativă** după număr, loc și timp, cu celule extensibile și trimiteri către aceleași fișe canonice.
12. **Stocare locală** în `Documente/IndexUniversal` (sau directorul indicat prin variabila `INDEX_UNIVERSAL_HOME`).

## Grila mnemonică extensibilă — Hugo de Saint-Victor

Modulul **Grilă mnemonică** este o *vedere de memorare* opțională, distinctă de indexul semantic. Se inspiră din *De tribus maximis circumstantiis gestorum*: o serie de locuri **numerotate**, asociate cu repere **spațiale** și **temporale**, pe care elevul le exersează pentru reamintire. În lucrare, autorul insistă și asupra persoanelor, locurilor și timpurilor istoriei. O grilă grafică digitală, cu celule extensibile, este o **adaptare contemporană**, nu o transcriere literală a unei interfețe medievale.

- Deschide **Grilă mnemonică** din bara de instrumente. Prima grilă este creată numai la prima utilizare; inițial are 24 locuri numerotate.
- **+ 10 celule** / **+ 50 celule** prelungește șirul indefinit; numerele identifică exclusiv **locuri mnemonice**, nu informațiile.
- Poți crea mai multe grile și alege numărul de coloane la crearea fiecăreia. Numărul de coloane rămâne stabil pentru memoria pozițională.
- Fiecare loc indică **o fișă deja existentă**, fără copierea conținutului. Poți adăuga un indiciu-imagine, un locus mental și un reper temporal, păstrate expres ca **ajutoare de memorie, nu fapte din surse**.
- Apasă butonul cu titlul fișei pentru a reveni direct la căutarea originală; pe fișa indexată apar automat și locurile mnemonice care trimit către ea.
- Datele mnemonice sunt salvate în aceeași bază SQLite și incluse în backup/restore. Indexarea în oglindă și criteriile libere **nu depind** de grilă; aceasta nu creează categorii sau ierarhii obligatorii.

**Referințe istorice:** Hugo de Saint-Victor, *De tribus maximis circumstantiis gestorum*; W. M. Green, „Hugo of St. Victor: De tribus maximis circumstantiis gestorum” (1943); Mary Carruthers, *The Book of Memory*, capitol despre sistemul mnemonic al lui Hugo. Descriere accesibilă: https://www.arsinq.com/hugh/.

## Ce NU face încă

- Nu indexează automat un PDF integral, nu produce lecturi semantice și nu inventează relații. Apare **numai ceea ce a fost introdus**.
- Nu răspunde semantic în limbaj natural la întrebări complexe: căutarea curentă este textuală peste relațiile structurate manual.
- Nu deduce automat relații tranzitive (de exemplu `Paris → Franța → Europa` nu devine `Paris → Europa` fără evidență/confirmare).
- Nu are încă import MARC/BIBFRAME/RDF, editor vizual de coordonate PDF, versiuni multiutilizator, control de autoritate pentru omonime sau test de scalare la milioane de relații.
- Nu garantează identificarea unei singure ocurențe când același fragment exact apare de mai multe ori pe aceeași pagină PDF. Pentru precizie, păstrează și paragraful/rândul; ancorarea vizuală prin dreptunghiuri va fi adăugată ulterior.
- La fiecare căutare apar 40 de rezultate, cu butonul **Mai multe** pentru restul; o listă de milioane nu poate încăpea simultan pe ecran.

## Instalare în Windows, fără Python (prin GitHub Actions)

1. Creează în GitHub un **repository nou, gol**: `Index-Universal-Windows`. Recomand **Private** dacă proiectul și biblioteca sunt personale.
2. Descarcă arhiva cu codul proiectului, **dezarhiveaz-o** și urcă **fișierele din interior**, nu arhiva ZIP: în rădăcină trebuie să existe `main.py`, `requirements.txt`, folderul `index_universal`, folderul `tests` și folderul ascuns `.github/workflows`.
3. La `Actions` găsești `Build Windows EXE`. Dacă nu pornește automat, alege `Run workflow`.
4. Când procesul s-a încheiat cu succes, descarcă din secțiunea **Artifacts** arhiva `IndexUniversal-Windows-EXE`.
5. Extrage `IndexUniversal.exe` și pornește-l în Windows. Nu are nevoie de Python pe calculatorul unde rulează. Este un executabil *unsigned*, deci Windows SmartScreen poate afișa un avertisment; folosește-l numai dacă ai verificat codul și sursa.
6. Documentele și indexul tău **nu sunt încărcate pe GitHub**; GitHub primește numai codul aplicației pentru compilare.

**Important:** acest proiect a fost verificat prin teste de bază SQLite și interfață pe Linux. Compilarea `.exe` pe Windows se face în GitHub Actions; până când acel build este verde, nu afirmăm că pachetul executabil Windows a fost testat.

## Rulare directă, pentru dezvoltare

Cu Python 3.12 instalat:

```powershell
python -m pip install -r requirements.txt
python main.py
```

## Operații de început

1. `+ Surse PDF / TXT` — importă sau leagă sursele originale.
2. `Catalog surse` — completează autorul, ediția și datele bibliografice.
3. `+ Informație` — creează, de exemplu, fișele `Europa`, `Clovis I`, `continent`, `Italia longobardă`.
4. `+ Relație` — scrie o relație *exactă*, sensul ei, contextul și orice criterii justificabile (exemplu: `perioadă: secolul al VI-lea`), apoi ancorează sursa.
5. Caută `Europa` și vei vedea relația introdusă prin oricare dintre capetele ei. Apasă **A** sau **B** pentru a vedea dovada originală; poți deschide două surse în paralel.
6. Creează fișe și pentru pagini, paragrafe, rânduri, intervale, cuvinte, texte integrale sau interpretări, dacă ai nevoie. Tipurile nu sunt impuse de aplicație.
7. Fă periodic `Salvează arhivă`, păstrând copiile de siguranță în afara calculatorului principal.

## Arhitectura tehnică

Python + Tkinter (desktop nativ), SQLite + FTS5, PyMuPDF (PDF) și Pillow (imagine). Toate rulează offline. Relațiile sunt salvate **o singură dată** ca subiect–predicat–obiect, cu context, statut, calificatori și surse; fiecare interogare reconstruiește prezentarea dinspre fișa căutată. Originalul rămâne în fișierul PDF/TXT, nu este rescris ca articol enciclopedic.

## Teste

```powershell
python -m unittest discover -s tests -v
```

Proiectul nu este afiliat Wikipedia sau Wikidata.
