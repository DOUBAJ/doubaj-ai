"""Interface translations: French, Arabic (RTL) and English."""
from __future__ import annotations

_LANG = "fr"

T: dict[str, dict[str, str]] = {
    # splash
    "by": {"fr": "Réalisé par Doubaj Ahmed", "ar": "من إعداد دباج أحمد", "en": "Created by Doubaj Ahmed"},
    "role": {"fr": "Professeur de technologie industrielle", "ar": "أستاذ مادة التكنولوجيا الصناعية",
             "en": "Industrial technology teacher"},
    "start": {"fr": "COMMENCER", "ar": "COMMENCER", "en": "COMMENCER"},
    "tagline": {"fr": "Assistant intelligent multi-modèles", "ar": "مساعد ذكي متعدد النماذج",
                "en": "Multi-model intelligent assistant"},
    "rights": {"fr": "Tous droits réservés : Doubaj Ahmed – DOUBAJ AHMED",
               "ar": "جميع الحقوق محفوظة: دباج أحمد – DOUBAJ AHMED",
               "en": "All rights reserved: Doubaj Ahmed – DOUBAJ AHMED"},
    # sidebar
    "new_chat": {"fr": "Nouvelle conversation", "ar": "محادثة جديدة", "en": "New chat"},
    "search_chats": {"fr": "Rechercher…", "ar": "بحث في المحادثات…", "en": "Search chats…"},
    "projects": {"fr": "Projets", "ar": "المشاريع", "en": "Projects"},
    "memory": {"fr": "Mémoire", "ar": "الذاكرة", "en": "Memory"},
    "settings": {"fr": "Paramètres", "ar": "الإعدادات", "en": "Settings"},
    "files": {"fr": "Fichiers créés", "ar": "الملفات المنشأة", "en": "Generated files"},
    "rename": {"fr": "Renommer", "ar": "إعادة التسمية", "en": "Rename"},
    "delete": {"fr": "Supprimer", "ar": "حذف", "en": "Delete"},
    "export": {"fr": "Exporter", "ar": "تصدير", "en": "Export"},
    "move_project": {"fr": "Associer à un projet", "ar": "ربط بمشروع", "en": "Move to project"},
    "no_project": {"fr": "Aucun projet", "ar": "بدون مشروع", "en": "No project"},
    "confirm_delete": {"fr": "Supprimer définitivement ?", "ar": "هل تريد الحذف نهائياً؟", "en": "Delete permanently?"},
    # top bar
    "provider": {"fr": "Fournisseur", "ar": "المزود", "en": "Provider"},
    "model": {"fr": "Modèle", "ar": "النموذج", "en": "Model"},
    "reasoning": {"fr": "Mode de raisonnement", "ar": "نمط التفكير", "en": "Reasoning mode"},
    "r_fast": {"fr": "Réponse rapide", "ar": "إجابة سريعة", "en": "Quick answer"},
    "r_standard": {"fr": "Analyse standard", "ar": "تحليل عادي", "en": "Standard analysis"},
    "r_deep": {"fr": "Analyse approfondie", "ar": "تحليل معمق", "en": "Deep analysis"},
    "mode": {"fr": "Espace", "ar": "الوضع", "en": "Mode"},
    "m_general": {"fr": "Général", "ar": "عام", "en": "General"},
    "m_education": {"fr": "Éducation", "ar": "تعليمي", "en": "Education"},
    "m_code": {"fr": "Programmation", "ar": "برمجة", "en": "Coding"},
    "online": {"fr": "En ligne", "ar": "عبر الإنترنت", "en": "Online"},
    "offline": {"fr": "Hors ligne", "ar": "دون إنترنت", "en": "Offline"},
    "theme": {"fr": "Thème clair / sombre", "ar": "الوضع الليلي / النهاري", "en": "Light / dark theme"},
    "workspace": {"fr": "Espace de travail", "ar": "مساحة العمل", "en": "Workspace"},
    # composer
    "placeholder": {"fr": "Écrivez votre demande… (Entrée = envoyer, Maj+Entrée = nouvelle ligne)",
                    "ar": "اكتب طلبك هنا… (Enter للإرسال، Shift+Enter لسطر جديد)",
                    "en": "Type your request… (Enter = send, Shift+Enter = new line)"},
    "attach": {"fr": "Joindre des fichiers", "ar": "إرفاق ملفات", "en": "Attach files"},
    "send": {"fr": "Envoyer", "ar": "إرسال", "en": "Send"},
    "stop": {"fr": "Arrêter", "ar": "إيقاف", "en": "Stop"},
    "web": {"fr": "Recherche web", "ar": "البحث في الإنترنت", "en": "Web search"},
    "tools": {"fr": "Outils IA", "ar": "أدوات الذكاء الاصطناعي", "en": "AI tools"},
    "voice": {"fr": "Dictée vocale", "ar": "الإدخال الصوتي", "en": "Voice input"},
    "gen_image": {"fr": "Générer une image…", "ar": "توليد صورة…", "en": "Generate an image…"},
    "run_code": {"fr": "Exécuter le dernier code Python", "ar": "تشغيل آخر كود Python", "en": "Run last Python code"},
    "add_memory": {"fr": "Ajouter à la mémoire…", "ar": "إضافة إلى الذاكرة…", "en": "Add to memory…"},
    # message actions
    "copy": {"fr": "Copier", "ar": "نسخ", "en": "Copy"},
    "regenerate": {"fr": "Régénérer", "ar": "إعادة التوليد", "en": "Regenerate"},
    "edit": {"fr": "Modifier et renvoyer", "ar": "تعديل وإعادة الإرسال", "en": "Edit & resend"},
    "read_aloud": {"fr": "Lire à voix haute", "ar": "قراءة بصوت مسموع", "en": "Read aloud"},
    "pause_resume": {"fr": "Pause / reprise lecture", "ar": "إيقاف / استئناف القراءة", "en": "Pause / resume"},
    "open_ws": {"fr": "Ouvrir dans l'espace de travail", "ar": "فتح في مساحة العمل", "en": "Open in workspace"},
    "copied": {"fr": "Copié", "ar": "تم النسخ", "en": "Copied"},
    "thinking": {"fr": "Réflexion…", "ar": "جارٍ التفكير…", "en": "Thinking…"},
    "searching": {"fr": "Recherche sur le web…", "ar": "جارٍ البحث في الإنترنت…", "en": "Searching the web…"},
    "reading": {"fr": "Lecture des documents…", "ar": "جارٍ قراءة المستندات…", "en": "Reading documents…"},
    "stopped": {"fr": "[Génération arrêtée]", "ar": "[تم إيقاف التوليد]", "en": "[Generation stopped]"},
    "error": {"fr": "Erreur", "ar": "خطأ", "en": "Error"},
    "welcome": {"fr": "Bonjour ! Comment puis-je vous aider aujourd'hui ?",
                "ar": "مرحباً! كيف يمكنني مساعدتك اليوم؟", "en": "Hello! How can I help you today?"},
    "welcome_sub": {"fr": "Posez une question, joignez un document, ou demandez un fichier Word, PowerPoint, Excel ou PDF.",
                    "ar": "اطرح سؤالاً، أو أرفق مستنداً، أو اطلب إنشاء ملف Word أو PowerPoint أو Excel أو PDF.",
                    "en": "Ask a question, attach a document, or ask for a Word, PowerPoint, Excel or PDF file."},
    "no_key": {"fr": "Aucune clé API pour ce fournisseur. Ouvrez Paramètres → Fournisseurs.",
               "ar": "لا يوجد مفتاح API لهذا المزود. افتح الإعدادات ← المزودون.",
               "en": "No API key for this provider. Open Settings → Providers."},
    "files_created": {"fr": "Fichiers créés", "ar": "الملفات المنشأة", "en": "Files created"},
    "open": {"fr": "Ouvrir", "ar": "فتح", "en": "Open"},
    "save_as": {"fr": "Enregistrer sous…", "ar": "حفظ باسم…", "en": "Save as…"},
    "preview": {"fr": "Aperçu", "ar": "معاينة", "en": "Preview"},
    "open_folder": {"fr": "Ouvrir le dossier", "ar": "فتح المجلد", "en": "Open folder"},
    "memory_suggest": {"fr": "L'assistant propose de mémoriser :", "ar": "يقترح المساعد حفظ المعلومة التالية:",
                       "en": "The assistant suggests remembering:"},
    "send_files_confirm": {"fr": "Les fichiers joints vont être envoyés au service en ligne « {p} ». Continuer ?",
                           "ar": "سيتم إرسال الملفات المرفقة إلى الخدمة الخارجية «{p}». هل تريد المتابعة؟",
                           "en": "Attached files will be sent to the online service \"{p}\". Continue?"},
    "run_confirm": {"fr": "Exécuter ce code Python dans le bac à sable (dossier temporaire isolé, 30 s max) ?",
                    "ar": "هل تريد تشغيل هذا الكود في بيئة معزولة (مجلد مؤقت، 30 ثانية كحد أقصى)؟",
                    "en": "Run this Python code in the sandbox (isolated temp folder, 30 s max)?"},
    # workspace
    "ws_preview": {"fr": "Aperçu", "ar": "معاينة", "en": "Preview"},
    "ws_code": {"fr": "Éditeur", "ar": "المحرر", "en": "Editor"},
    "ws_files": {"fr": "Fichiers", "ar": "الملفات", "en": "Files"},
    "ws_output": {"fr": "Console", "ar": "المخرجات", "en": "Console"},
    "ws_run": {"fr": "Exécuter / Aperçu", "ar": "تشغيل / معاينة", "en": "Run / Preview"},
    "ws_improve": {"fr": "Demander une amélioration", "ar": "طلب تحسين", "en": "Ask for improvement"},
    "ws_browser": {"fr": "Ouvrir dans le navigateur", "ar": "فتح في المتصفح", "en": "Open in browser"},
    "ws_save": {"fr": "Enregistrer", "ar": "حفظ", "en": "Save"},
    "improve_prompt": {"fr": "Améliore ce contenu :", "ar": "حسّن هذا المحتوى:", "en": "Improve this content:"},
    # settings
    "providers": {"fr": "Fournisseurs IA", "ar": "مزودو الذكاء الاصطناعي", "en": "AI providers"},
    "general": {"fr": "Général", "ar": "عام", "en": "General"},
    "api_key": {"fr": "Clé API", "ar": "مفتاح API", "en": "API key"},
    "base_url": {"fr": "URL du service", "ar": "عنوان الخدمة", "en": "Base URL"},
    "default_model": {"fr": "Modèle par défaut", "ar": "النموذج الافتراضي", "en": "Default model"},
    "test": {"fr": "Tester la connexion", "ar": "اختبار الاتصال", "en": "Test connection"},
    "refresh_models": {"fr": "Actualiser les modèles", "ar": "تحديث قائمة النماذج", "en": "Refresh models"},
    "language": {"fr": "Langue", "ar": "اللغة", "en": "Language"},
    "dark_mode": {"fr": "Mode sombre", "ar": "الوضع الليلي", "en": "Dark mode"},
    "temperature": {"fr": "Créativité (température)", "ar": "درجة الإبداع", "en": "Creativity (temperature)"},
    "auto": {"fr": "Automatique", "ar": "تلقائي", "en": "Automatic"},
    "length": {"fr": "Longueur des réponses", "ar": "طول الإجابات", "en": "Answer length"},
    "l_short": {"fr": "Courtes", "ar": "قصيرة", "en": "Short"},
    "l_normal": {"fr": "Normales", "ar": "عادية", "en": "Normal"},
    "l_long": {"fr": "Détaillées", "ar": "مفصلة", "en": "Detailed"},
    "max_tokens": {"fr": "Tokens max. par réponse", "ar": "الحد الأقصى للرموز في الإجابة", "en": "Max tokens per answer"},
    "context_chars": {"fr": "Contexte envoyé (caractères)", "ar": "حجم السياق المرسل (حروف)", "en": "Context sent (characters)"},
    "web_backend": {"fr": "Moteur de recherche", "ar": "محرك البحث", "en": "Search engine"},
    "local_models": {"fr": "Modèles locaux", "ar": "النماذج المحلية", "en": "Local models"},
    "voice_tab": {"fr": "Voix", "ar": "الصوت", "en": "Voice"},
    "images_tab": {"fr": "Images", "ar": "الصور", "en": "Images"},
    "privacy": {"fr": "Confidentialité & sécurité", "ar": "الخصوصية والأمان", "en": "Privacy & security"},
    "memory_enabled": {"fr": "Activer la mémoire", "ar": "تفعيل الذاكرة", "en": "Enable memory"},
    "confirm_upload": {"fr": "Demander avant d'envoyer des fichiers à un service en ligne",
                       "ar": "طلب الإذن قبل إرسال الملفات إلى خدمة خارجية",
                       "en": "Ask before sending files to an online service"},
    "sandbox_restricted": {"fr": "Bac à sable restreint pour le code (recommandé)",
                           "ar": "بيئة تنفيذ مقيدة للأكواد (موصى به)",
                           "en": "Restricted code sandbox (recommended)"},
    "backup": {"fr": "Sauvegarder les données…", "ar": "نسخ احتياطي للبيانات…", "en": "Back up data…"},
    "delete_all": {"fr": "Supprimer toutes les conversations", "ar": "حذف جميع المحادثات", "en": "Delete all conversations"},
    "save": {"fr": "Enregistrer", "ar": "حفظ", "en": "Save"},
    "cancel": {"fr": "Annuler", "ar": "إلغاء", "en": "Cancel"},
    "close": {"fr": "Fermer", "ar": "إغلاق", "en": "Close"},
    "add": {"fr": "Ajouter", "ar": "إضافة", "en": "Add"},
    "name": {"fr": "Nom", "ar": "الاسم", "en": "Name"},
    "description": {"fr": "Description", "ar": "الوصف", "en": "Description"},
    "instructions": {"fr": "Instructions du projet", "ar": "تعليمات المشروع", "en": "Project instructions"},
    "project_files": {"fr": "Documents de référence", "ar": "الوثائق المرجعية", "en": "Reference documents"},
    "project_chats": {"fr": "Conversations", "ar": "المحادثات", "en": "Conversations"},
    "project_outputs": {"fr": "Résultats créés", "ar": "النتائج المنشأة", "en": "Created outputs"},
    "new_project": {"fr": "Nouveau projet", "ar": "مشروع جديد", "en": "New project"},
    "active_project": {"fr": "Projet actif", "ar": "المشروع النشط", "en": "Active project"},
    "ok_conn": {"fr": "Connexion réussie", "ar": "تم الاتصال بنجاح", "en": "Connection OK"},
    "fail_conn": {"fr": "Échec de la connexion", "ar": "فشل الاتصال", "en": "Connection failed"},
    "key_secure": {"fr": "Clés chiffrées avec", "ar": "المفاتيح مشفرة بواسطة", "en": "Keys encrypted with"},
    "ram_info": {"fr": "Mémoire RAM du PC", "ar": "ذاكرة RAM للحاسوب", "en": "PC RAM"},
    "local_help": {
        "fr": "Le mode hors ligne utilise Ollama (recommandé) ou un serveur llama.cpp. Installez Ollama depuis ollama.com, "
              "puis téléchargez un modèle ci-dessous ou importez un fichier GGUF. Règle pratique : un modèle 7-8B quantifié "
              "(Q4) demande ≈ 5 Go de RAM/VRAM, 13-14B ≈ 9 Go, 30-34B ≈ 20 Go. La qualité dépend de la taille du modèle "
              "et de la puissance du PC.",
        "ar": "يعتمد الوضع دون إنترنت على Ollama (موصى به) أو خادم llama.cpp. ثبّت Ollama من ollama.com ثم حمّل نموذجاً من "
              "الأسفل أو استورد ملف GGUF. قاعدة تقريبية: نموذج 7-8B مضغوط (Q4) يحتاج ≈ 5 جيغابايت من RAM/VRAM، و13-14B ≈ 9، "
              "و30-34B ≈ 20 جيغابايت. جودة الإجابات تعتمد على حجم النموذج وقوة الحاسوب.",
        "en": "Offline mode uses Ollama (recommended) or a llama.cpp server. Install Ollama from ollama.com, then pull a "
              "model below or import a GGUF file. Rule of thumb: a quantised (Q4) 7-8B model needs ≈ 5 GB RAM/VRAM, "
              "13-14B ≈ 9 GB, 30-34B ≈ 20 GB. Quality depends on model size and PC power."},
    "pull_model": {"fr": "Télécharger le modèle", "ar": "تحميل النموذج", "en": "Pull model"},
    "import_gguf": {"fr": "Importer un fichier GGUF…", "ar": "استيراد ملف GGUF…", "en": "Import GGUF file…"},
    "installed_models": {"fr": "Modèles installés (Ollama)", "ar": "النماذج المثبتة (Ollama)", "en": "Installed models (Ollama)"},
    "image_prompt": {"fr": "Décrivez l'image à générer :", "ar": "صف الصورة المطلوب توليدها:", "en": "Describe the image to generate:"},
    "listening": {"fr": "Enregistrement… cliquez pour arrêter", "ar": "جارٍ التسجيل… انقر للإيقاف", "en": "Recording… click to stop"},
    "tts_voice": {"fr": "Voix de lecture", "ar": "صوت القراءة", "en": "Reading voice"},
    "tts_rate": {"fr": "Vitesse de lecture", "ar": "سرعة القراءة", "en": "Speech rate"},
    "stt_service": {"fr": "Service de transcription (compatible OpenAI)", "ar": "خدمة تحويل الصوت إلى نص (متوافقة مع OpenAI)",
                    "en": "Transcription service (OpenAI-compatible)"},
    "img_service": {"fr": "Service de génération d'images (compatible OpenAI)",
                    "ar": "خدمة توليد الصور (متوافقة مع OpenAI)", "en": "Image generation service (OpenAI-compatible)"},
    "same_as_openai": {"fr": "Laisser vide pour utiliser la clé OpenAI", "ar": "اتركه فارغاً لاستعمال مفتاح OpenAI",
                       "en": "Leave empty to use the OpenAI key"},
    "about": {"fr": "À propos", "ar": "حول التطبيق", "en": "About"},
    "memory_disabled": {"fr": "La mémoire est désactivée.", "ar": "الذاكرة معطلة.", "en": "Memory is disabled."},
    "edit_memory": {"fr": "Modifier", "ar": "تعديل", "en": "Edit"},
    "clear_all": {"fr": "Tout effacer", "ar": "مسح الكل", "en": "Clear all"},
    "global": {"fr": "Globale", "ar": "عامة", "en": "Global"},
    "tokens_used": {"fr": "tokens", "ar": "رمز", "en": "tokens"},
    "doc_warning": {"fr": "Avertissement", "ar": "تنبيه", "en": "Warning"},
}


def set_lang(lang: str) -> None:
    global _LANG
    _LANG = lang if lang in ("fr", "ar", "en") else "fr"


def lang() -> str:
    return _LANG


def is_rtl() -> bool:
    return _LANG == "ar"


def tr(key: str, **kw) -> str:
    entry = T.get(key)
    if not entry:
        return key
    s = entry.get(_LANG) or entry.get("fr") or key
    return s.format(**kw) if kw else s


VERSE = ("وَقُلِ اعْمَلُوا فَسَيَرَى اللَّهُ عَمَلَكُمْ وَرَسُولُهُ وَالْمُؤْمِنُونَ ۖ وَسَتُرَدُّونَ إِلَىٰ عَالِمِ الْغَيْبِ "
         "وَالشَّهَادَةِ فَيُنَبِّئُكُم بِمَا كُنتُمْ تَعْمَلُونَ")
VERSE_REF = "سورة التوبة – الآية 105"
