# Asset Esterni - Guida

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
