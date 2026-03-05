# Asset Esterni - Guida

## Menu principale - Titolo
- **File:** `assets/title.png`
  - Dimensione: 1376x768 pixel
  - Immagine del titolo "SATAN'S FALL" del menu principale
  - Se non presente, il gioco userà il rendering testuale come fallback automatico
  - Implementazione: `src/ui.py` → `_load_title_image()` + `draw_main_menu()`

---

- L'opacità e il colore sono ora configurabili tramite le costanti
  `PURGATORY_OVERLAY_ALPHA` e `PURGATORY_OVERLAY_COLOR` in
  `src/game_constants.py`.  Il valore predefinito è un alpha di 60 con colore
  grigio (200,200,200), ma può essere aumentato o diminuito se si desidera un
  effetto più marcato o più leggero.  (Non ci sono particelle laterali.)
- Non sono necessari asset esterni: il riempimento viene creato dinamicamente.

Il gioco ora supporta l'uso di immagini personalizzate per sostituire le forme geometriche predefinite!

## Come Usare le Immagini

1. Crea o ottieni le tue immagini (formato PNG, JPG o GIF)
2. Metti le immagini nella cartella `assets/`
3. Usa i nomi dei file indicati sotto
4. Il gioco caricherà automaticamente le immagini disponibili

**Nota:** Se un'immagine non viene trovata, il gioco userà le forme geometriche predefinite come fallback.

## Nomi File Supportati

### Personaggio Giocatore (Satan)
- **File:** `assets/satan.png`
- **Dimensione consigliata:** 80x100 pixel
- Rappresenta il personaggio principale

### Nemici
- **File:** `assets/enemy_weak.png`
  - Dimensione: 40x40 pixel
  - Nemico debole (zombie)

- **File:** `assets/enemy_normal.png`
  - Dimensione: 40x40 pixel
  - Nemico normale (esorcist)

- **File:** `assets/enemy_inquisitor.png`
  - Dimensione: 40x40 pixel
  - Nemico normale (inquisitor)

- **File:** `assets/enemy_strong.png`
  - Dimensione: 40x40 pixel
  - Nemico forte (soldier)

- **File:** `assets/enemy_angel.png`
  - Dimensione: 40x40 pixel
  - Angelo volante (tipo speciale)

- **File:**  enemy_winged.png

- **File:** `assets/enemy_giant.png`

- **File:** `assets/enemy_crusader.png`
  - Dimensione: 60x60 pixel
  - Nemico gigante (spawn ogni 12 secondi)

- **File:** `assets/enemy_pentagram.png`
  - Dimensione consigliata: 80x80 pixel
  - Nemico tank a forma di stella a 5 punte (pentacolo)
  - Appare una volta per stage dopo 60 secondi
  - Attraversa lo stage orizzontalmente con oscillazione verticale
  - Non attacca (danni = 0)
  - Se assente, il gioco renderizza un pentacolo rosso/oro con arte vettoriale

### Boss
- **File:** `assets/boss_small.png`
  - Dimensione: 60x60 pixel
  - Boss piccolo

- **File:** `assets/boss_medium.png`
  - Dimensione: 80x80 pixel
  - Boss medio (viola)

- **File:** `assets/boss_big.png`
  - Dimensione: 120x120 pixel
  - Boss grande (figura divina)

- **File:** `assets/boss_final.png`
  - Dimensione: 150x150 pixel
  - Boss finale (gesù)

### Proiettili
- **File:** `assets/projectile.png`
  - Dimensione: 20x20 pixel
  - Proiettili del giocatore

- **File:** `assets/enemy_projectile.png`
  - Dimensione: 20x20 pixel
  - Proiettili dei nemici

### Edifici PROLOGUE (Cattedrali e Chiese)
- **File:** `assets/cathedral_center.png`
  - Dimensione consigliata: 100x100 pixel
  - Cattedrale centrale (più grande, con torri laterali)
  - Posizionata al centro del livello PROLOGUE

- **File:** `assets/church_left.png`
  - Dimensione consigliata: 60x60 pixel
  - Chiesa laterale sinistra
  - Posizionata a sinistra nel livello PROLOGUE

- **File:** `assets/church_right.png`
  - Dimensione consigliata: 60x60 pixel
  - Chiesa laterale destra
  - Posizionata a destra nel livello PROLOGUE

- **File:** `assets/church_outer_left.png`
  - Dimensione consigliata: 60x60 pixel
  - Chiesa esterna sinistra
  - Posizionata al lato più esterno sinistro del livello PROLOGUE

- **File:** `assets/church_outer_right.png`
  - Dimensione consigliata: 60x60 pixel
  - Chiesa esterna destra
  - Posizionata al lato più esterno destro del livello PROLOGUE

### Campo di battaglia (Limbo)
- **File:** `assets/limbo_battlefield.png`
  - Dimensione consigliata: 1280x720 (verrà ridimensionata automaticamente)
  - Immagine di sfondo per la parte interna delle mura nei livelli `limbo`, `limbo_2`, `limbo_3` e `limbo_final`.
  - La variante `limbo_final` utilizza lo stesso sfondo ma introduce un boss dopo 3 minuti.
  - Se mancante, il gioco userà il riempimento arancione di default.
- **External background:**
  - **File:** `assets/limbo_background.png`
  - Copre tutta la schermata esterna alle mura, come avviene per prologo e purgatorio.
  - Se l'immagine manca, il gioco ricaverà la tinta da `bg_color`.

### Campo di battaglia (Purgatory)

### Limbo Final boss
- **File:** `assets/boss_limbo.png`
  - Sprite opzionale per il boss che appare in `limbo_final` al minuto 3.
  - Se non presente, il boss verrà disegnato con arte vettoriale generica.
  - Puoi generare un'immagine di test con lo script
    `tools/generate_limbo_boss_asset.py` oppure fornire la tua grafica
    mantenendo lo stesso nome e dimensione base (120×120).

### Campo di battaglia (Purgatory)
- **File:** `assets/purgatory_battlefield.png`
  - Dimensione consigliata: 1280x720 (ridimensionata automaticamente dal gestore asset)
  - Immagine di sfondo per la parte interna delle mura nei livelli `purgatory`, `purgatory_2` e `purgatory_3`.
  - La grafica viene ritagliata alla forma interna delle mura oblique, proprio come accade per il campo di battaglia in Limbo o Prologo.
  - Se non presente, viene usato il colore grigio di default.
- **File:** `assets/purgatory_background.png`
  - Dimensione consigliata: 1280x720
  - Sfondo esterno (cielo / nubi ecc.) per i livelli purgatory; viene disegnata sull'intero schermo.
  - Questo asset è completamente independentemente dall'immagine "campo di battaglia".
    anche se non è presente nessuna immagine di campo, l'esterno rimane visibile;
    l'interno delle mura verrà comunque riempito con il `floor_color`.
  - In assenza dell'immagine esterna si usa il colore nero configurato in `STAGE_SETTINGS`.

### Statue / Torri
- **File:** `assets/statue_fire.png`
  - Dimensione consigliata: circa 120‑140 pixel in altezza, 40‑60 pixel in larghezza
    (il gioco non esegue ridimensionamenti automatici). L'immagine viene ancorata in
    basso al centro della statua/torre; assicurati quindi che la parte inferiore del
    disegno corrisponda al "piede" della statua.  Qualunque proporzione verticale è
    accettata, ma usare un'altezza simile a quella del disegno vettoriale (circa
    130px) aiuta a mantenere il posizionamento corretto.
    Se il tuo asset sembra posizionarsi troppo in alto, puoi modificare il valore
    `STATUE_ASSET_VERTICAL_OFFSET` in `src/game_constants.py`.  Viene inizialmente
    impostato a 100 per compensare la prima statua importata; riducilo o aumentalo
    in base alle tue immagini.

    Questo offset non si applica solamente alle immagini importate: la stessa
    costante sposta anche l'arte vettoriale utilizzata quando un asset non è
    presente.  In questo modo tutte le statue (Limbo, Purgatory, Hell) si allineano
    verticalmente senza dover cambiare più valori separati.

    > **Nota sulla posizione dei proiettili:**
    > I proiettili sparati dalle statue non partono esattamente dall'asse delle
    > loro basi, bensì vengono spostati leggermente verso il centro dello schermo
    > e un poco verso il basso per migliorare l'allineamento visivo con le
    > statue. Questo scostamento dipende dalla fase affrontata:
    >
    > * **Limbo** – 30 px verso il centro, 10 px verso il basso.
    > * **Purgatory** e **Hell** – 10 px verso il centro, 10 px verso il basso.
    >
    > Tutti i valori sono configurabili in `src/game_constants.py` tramite le
    > costanti `STATUE_PROJECTILE_OFFSET_X_LIMBO`,
    > `STATUE_PROJECTILE_OFFSET_X_PURGATORY`,
    > `STATUE_PROJECTILE_OFFSET_X_HELL` e
    > `STATUE_PROJECTILE_OFFSET_Y`.
    >
    > Per garantire che i proiettili appaiano come se venissero sparati da dietro
    > le statue, il motore disegna sempre le statue di Limbo su un livello
    > superiore rispetto ai proiettili.  Questa modifica impedisce ai colpi di
    > apparire improvvisamente "davanti" alla statua mentre vengono generati.
  - Sostituisce il disegno vettoriale delle statue di fuoco sia nelle pedane di
    Limbo che sulle torri di Purgatorio/Hell.
- **File:** `assets/statue_storm.png`
  - Simile a `statue_fire.png`, ma utilizzata per le statue/torri di tipo "storm".
- **File:** `assets/statue_ice.png`
  - Immagine alternativa per le statue/torri di tipo "ice".
  - Se le immagini non sono presenti, il gioco ricade automaticamente sulle forme
    geometriche colorate.

## Consigli per le Immagini

- **Formato:** PNG con sfondo trasparente è l'ideale
- **Risoluzione:** Usa le dimensioni consigliate o multipli (saranno ridimensionate automaticamente)
- **Stile:** Mantieni uno stile coerente per tutti gli asset
- **Colori:** Considera il background scuro del gioco (#140a1e)

## Esempio di Struttura

```
satans fall/
├── assets/
│   ├── satan.png
│   ├── enemy_weak.png
│   ├── enemy_normal.png
│   ├── boss_final.png
│   ├── projectile.png
│   ├── cathedral_center.png
│   ├── church_left.png
│   └── church_right.png
├── main_pygame.py
└── ...
```

## Testare le Immagini

Dopo aver aggiunto le immagini:
1. Avvia il gioco: `python main_pygame.py`
2. Le immagini caricate appariranno al posto delle forme
3. Se vedi errori nella console, controlla i nomi dei file e i formati

## Generare Icone Automatiche

Se preferisci non creare manualmente i file per ogni arma, puoi sfruttare il
contenuto dei proiettili per generare automaticamente le icone.  Esegui lo
script seguente dalla radice del progetto:

```sh
python scripts/generate_weapon_icons.py
```

Il programma produrrà una PNG per ogni voce definita in
`src/weapons.py` (nomi convertiti in minuscolo).  Gli asset esistenti verranno
sovrascritti.

## Rimuovere Immagini

Per tornare alle forme geometriche, basta rimuovere o rinominare i file dalla cartella `assets/`.

### Icone Upgrade

### Icone Armi

- **File pattern:** `assets/weapon_<id>.png`
  - Artwork displayed beside each entry in the weapon selection screen.  A
    fixed square on the left of each choice is reserved even if the file is
    missing, so the text alignment remains consistent.
  - **Important:** icons are expected to be **transparent** where no graphic
    is needed; do **not** draw a filled background.  Imported assets will
    look better with clear regions.
  - `<id>` should match the internal weapon identifier used in
    `src/weapons.py` (case sensitive).

  Esempi di nomi attualmente definiti nell'asset manager:

  - `weapon_shotgun.png`  (Hellgun)
  - `weapon_orbital.png`  (Orbitals)
  - `weapon_spear.png`    (Spear)
  - `weapon_flies.png`    (Flies)
  - `weapon_beast.png`    (The number of the beast)
  - `weapon_skullboom.png`
  - `weapon_demonstrike.png` (DemonStrike)
  - `weapon_tenebrae.png` (Tenebrae)

For the Tenebrae weapon the actual projectile graphic may be placed in
`assets/tenebrae.png`; the code will also fall back to
`weapon_tenebrae.png` if the former is missing.  This mirrors the icon
naming and lets you share a single file for both purposes if desired.

  In futuro altri armi possono essere aggiunte seguendo lo stesso schema.

- **File:** `assets/icon_damage.png`
  - Dimensione: 64x64 pixel
  - Icona per upgrade Danno

- **File:** `assets/icon_fire_rate.png`
  - Dimensione: 64x64 pixel
  - Icona per upgrade Velocità di fuoco

- **File:** `assets/icon_piercing.png`
  - Dimensione: 64x64 pixel
  - Icona per upgrade Perforazione

- **File:** `assets/icon_bounce.png`
  - Dimensione: 64x64 pixel
  - Icona per upgrade Rimbalzo

- **File:** `assets/icon_area.png`
  - Dimensione: 64x64 pixel
  - Icona per upgrade Area

- **File:** `assets/icon_speed.png`
  - Dimensione: 64x64 pixel
  - Icona per upgrade Velocità proiettile
