# Asset Esterni - Guida

*Nota: i muri nei vari livelli usano ora un grigio scuro uniforme; la
modifica non richiede immagini esterne.*

### Nebbia di Purgatory
I livelli di Purgatory hanno una copertura di nebbia statica grigia che viene
sovrapposta all'intero schermo **dopo** che le mura e gli oggetti sono stati
Disegnati, garantendo che persino i muri si vedano attraverso la foschia. La
versione attuale non usa più particelle volumetriche laterali; l'effetto è
realizzato esclusivamente con un semplice overlay semi‑trasparente.

In aggiunta, un effetto più recente disegna **nuvole ovali molto grandi** che
fluttuano nella metà superiore dello stage (dove i nemici compaiono).  Le
nuvole nascono parzialmente tagliate dalla parte alta dello schermo — la
costante `PURGATORY_CLOUD_SPAWN_Y_RANGE` include valori negativi per
generarle oltre il bordo superiore — e rimangono confinate nella porzione
superiore (15 % dell'altezza). Sono molto trasparenti: l'opacità base è
controllata da `PURGATORY_CLOUD_ALPHA` (e i dossi irregolari da
`PURGATORY_CLOUD_BUMP_ALPHA`).  La frequenza di apparizione è regolata da
`PURGATORY_CLOUD_SPAWN_RATE`; per abbassare ancora la quantità basta ridurre
questa costante (ora impostata a circa 0.033 per ridurre il numero di nuvole di
un terzo rispetto al valore precedente).  Le precedenti "nuvole" sono state sostituite da un nuovo sistema di
particelle più morbido e volumetrico.  Vengono mantenute un numero fisso di
particelle (attualmente 12, regolabile tramite la costante `FOG_PARTICLE_COUNT`),
ognuna con una texture sfumata generata al runtime.  Si muovono lentamente in
orizzontale e oscillano verticalmente in modo sinusoidale; quando escono dal
lato destro ricompaiono a sinistra.  I parametri principali (numero, dimensione
del texture, velocità, ampiezza, ofset di timer, colore e alpha) si trovano
nelle costanti `FOG_*` di `src/game_constants.py`.

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

- **File:** `assets/enemy_giant.png`
  - Dimensione: 60x60 pixel
  - Nemico gigante (spawn ogni 12 secondi)

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
  - Immagine di sfondo per la parte interna delle mura nei livelli `limbo`, `limbo_2`, `limbo_3`.
  - Se mancante, il gioco userà il riempimento arancione di default.

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

## Rimuovere Immagini

Per tornare alle forme geometriche, basta rimuovere o rinominare i file dalla cartella `assets/`.

### Icone Upgrade
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
