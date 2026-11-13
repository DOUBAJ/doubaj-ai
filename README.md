# DOUBAJ AI

**Assistant intelligent de bureau, portable, pour Windows 10/11.**
Réalisé par **Doubaj Ahmed** – Professeur de technologie industrielle.
من إعداد **دباج أحمد** – أستاذ مادة التكنولوجيا الصناعية.

> DOUBAJ AI est une application cliente : l'intelligence vient du modèle choisi (Anthropic Claude, OpenAI,
> Google Gemini, un service compatible OpenAI, ou un modèle local via Ollama / llama.cpp / LM Studio).
> L'application ne prétend pas posséder son propre modèle.

## Obtenir l'exécutable `DOUBAJ AI.exe`

### Option A – GitHub Actions (recommandé, rien à installer)
1. Poussez ce dossier dans un dépôt GitHub.
2. Le workflow `.github/workflows/build-windows.yml` se lance sur `windows-latest` : il exécute les tests,
   construit l'EXE avec PyInstaller, vérifie qu'il démarre, puis produit **`DOUBAJ AI PORTABLE.zip`**.
3. Téléchargez-le dans l'onglet **Actions → dernier run → Artifacts**
   (ou dans **Releases** si vous poussez un tag `v1.0.0`).

### Option B – sur un PC Windows
Installez Python 3.12 (64 bits), puis double-cliquez sur `build_windows.bat`.
Résultat : `dist\DOUBAJ AI PORTABLE.zip`.

### Lancer depuis les sources (développement)
```bash
pip install -r requirements.txt
python main.py
```

## Contenu du ZIP
```
DOUBAJ AI PORTABLE/
├── DOUBAJ AI.exe          ← double-cliquer
├── _internal/             ← bibliothèques (Python, Qt…) – ne pas supprimer
├── data/                  ← vos conversations, projets, fichiers (créé automatiquement)
└── LISEZ-MOI - اقرأني.txt
```

## Fonctionnalités et état réel

| Domaine | État | Détails |
|---|---|---|
| Écran d'accueil (logo, verset, auteur, COMMENCER) | ✅ | Police Amiri (OFL) intégrée, choix FR/ع/EN |
| Chat en streaming, arrêt, régénérer, modifier & renvoyer, copier | ✅ | |
| Multi-fournisseurs | ✅ | Claude (SDK officiel, thinking adaptatif), OpenAI, Gemini, Ollama, llama.cpp, LM Studio, tout service compatible OpenAI |
| Mode de raisonnement (rapide / standard / approfondi) | ✅ | Mappé sur `effort` (Claude), `reasoning_effort` (OpenAI/Gemini) + consigne de style pour les autres |
| Markdown, tableaux, code coloré | ✅ | Formules LaTeX : rendu simplifié (symboles, fractions, indices), pas de moteur TeX complet |
| Historique SQLite : renommer, supprimer, rechercher, exporter (MD/JSON/DOCX) | ✅ | |
| Lecture PDF, DOCX, PPTX, XLSX, XLS, CSV, TXT, MD, JSON, HTML, code, images | ✅ | Marqueurs [Page n]/[Slide n]/[§n] pour citer la source |
| PDF scannés / images | ✅ | Envoyés comme images à un modèle avec vision (OCR par le modèle) |
| DOC (ancien Word) | ⚠️ | Via Microsoft Word si installé, sinon extraction dégradée |
| Création de fichiers réels DOCX, PDF, PPTX (tableaux, graphiques, schémas), XLSX (formules, graphiques), CSV, HTML, MD, TXT, projets ZIP | ✅ | Le modèle écrit un bloc `doubaj-file`, l'application génère le fichier |
| Images dans les PowerPoint | ⚠️ | Schémas, tableaux et graphiques natifs ; pas encore d'insertion automatique d'images générées |
| Espace de travail (aperçu HTML/JS/CSS, PDF, éditeur de code coloré, console) | ✅ | |
| Exécution de code Python isolée (confirmation, dossier temporaire, 30 s) | ✅ | Bac à sable « au mieux », pas une barrière de sécurité absolue. Dans l'EXE, seules les bibliothèques intégrées sont disponibles |
| Projets (instructions, documents de référence, conversations, résultats) | ✅ | Recherche des passages pertinents si les documents dépassent le contexte |
| Mémoire (proposée par l'IA, validée par l'utilisateur, modifiable, désactivable) | ✅ | |
| Recherche web avec sources | ✅ | DuckDuckGo sans clé ; Tavily/Brave avec clé |
| Vision (analyse d'images, schémas électriques) | ✅ | Dépend d'un modèle qui supporte la vision |
| Génération d'images | ✅ | Service compatible OpenAI (clé nécessaire) |
| Lecture vocale (TTS) | ✅ | Voix Windows hors ligne, pause/reprise |
| Dictée vocale (STT) | ✅ | Service compatible OpenAI (Whisper, Groq…) – clé nécessaire |
| Modèles locaux : liste, taille, RAM nécessaire, téléchargement, import GGUF | ✅ | Ollama doit être installé séparément (ollama.com) |
| Clés API chiffrées (Windows DPAPI), jamais journalisées | ✅ | |
| Interface FR / AR (RTL) / EN, thèmes clair/sombre | ✅ | |

## Architecture
```
main.py                       point d'entrée (+ mode --run-python pour le bac à sable)
doubaj/
  providers/                  base.py (interface commune) + anthropic, openai_compat (OpenAI, Gemini, Ollama…), registry
  core/                       engine (prompt, contexte, recherche dans les documents), settings, secrets, markdown
  documents/                  reader (lecture), generator (création de fichiers)
  storage/db.py               SQLite
  tools/                      web_search, sandbox, media (STT, images)
  ui/                         splash, main_window, chat_widgets, workspace, dialogs, theme, logo
tests/                        test_core.py (mock serveurs), test_ui.py (test de l'interface)
build/                        doubaj.spec, make_icon.py, package.py
```
Ajouter un fournisseur : créer une classe `Provider` et l'ajouter à `providers/registry.py`.

## Tests
```bash
cd tests && python test_core.py   # fournisseurs (serveurs simulés), documents, stockage
cd tests && python test_ui.py     # interface complète, captures dans tests/shots/
```

Police Amiri : SIL Open Font License (voir `doubaj/assets/fonts/OFL-Amiri.txt`).

Tous droits réservés : Doubaj Ahmed – DOUBAJ AHMED.
