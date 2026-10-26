import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

const en = {
  brand: "EvalBot",
  nav_dashboard: "Dashboard", nav_new: "New interview", nav_history: "My interviews", nav_jobs: "Jobs",
  nav_settings: "Settings", nav_quick: "Analyze a recording", sign_out: "Sign out", sign_in: "Sign in", sign_up: "Create account",
  get_started: "Get started", loading: "Loading…", save: "Save", saved: "Saved", cancel: "Cancel", delete: "Delete",
  edit: "Edit", back: "Back", continue: "Continue", retry: "Try again", copy: "Copy", copied: "Copied", theme_dark: "Dark theme",
  theme_light: "Light theme", language: "Language", min: "min", sec: "sec", of: "of", or: "or", optional: "optional",
  error_generic: "Something went wrong. Try again in a moment.",

  hero_title: "Practice the interview before the interview.",
  hero_sub: "EvalBot asks you real questions for your track, listens to how you answer, and shows you exactly what to fix. Its delivery scores are trained on how panels of human interviewers judged 138 real interviews.",
  cta_candidate: "Start a practice interview", cta_company: "Hire with EvalBot",
  demo_asking: "EvalBot is asking", demo_question: "Tell me about a data pipeline you built, and what broke first.",
  demo_listening: "Listening", demo_you: "You", demo_answer: "We ingested sensor data through Kafka. The first thing that broke was…",
  demo_content: "Content", demo_delivery: "Delivery", demo_structure: "Structure",
  for_candidates: "For job seekers", for_companies: "For hiring teams",
  c1_t: "Any track, any level", c1_d: "Data, backend, design, sales, HR and 25 more tracks, from internship to lead. Paste a job description or your CV and the questions follow it.",
  c2_t: "A real conversation", c2_d: "Questions are read aloud and you answer out loud. When an answer leaves something open, EvalBot asks a follow-up, like a real interviewer would.",
  c3_t: "Feedback you can act on", c3_d: "Every answer gets a score, what worked, what to improve, and a stronger version of what you said, built from your own facts.",
  c4_t: "See yourself improve", c4_d: "Your scores, speaking pace and filler words are tracked across interviews, with a learning plan for your track.",
  r1_t: "Send one link", r1_d: "Create a job with your own questions or AI-suggested ones, and share a single link with applicants.",
  r2_t: "Same interview for everyone", r2_d: "Every applicant answers the same questions with the same time limit, whenever it suits them.",
  r3_t: "A ranked shortlist with reasons", r3_d: "Candidates are ordered by score, each with a written assessment, the recordings and the transcript.",
  r4_t: "Your team decides", r4_d: "Shortlist, reject, rate and leave notes. EvalBot informs the decision; people make it.",
  science_title: "Scored like a panel of interviewers",
  science_text: "We trained EvalBot's delivery scores on the MIT Interview Dataset: 138 recorded mock interviews, each rated by nine people. Tested on people it never saw, EvalBot matches or beats a single human rater on filler words, structure, calmness and pauses, and comes close on enthusiasm and the hiring recommendation.",
  science_model: "EvalBot", science_human: "A single human rater",
  science_note: "Correlation with the panel average, person-grouped cross-validation.",
  how_title: "How a practice interview works",
  how_1: "Pick your track, level and interview style.", how_2: "Answer each question out loud, with your camera on or off.",
  how_3: "Get a full report a minute later, in English or Arabic.",
  tracks_title: "30 career tracks",
  footer_text: "EvalBot started as a graduation project at the Faculty of Computers and Artificial Intelligence, Benha University.",
  footer_privacy: "Your recordings are only visible to you and, for job interviews, to the company you applied to.",

  auth_signin_title: "Welcome back", auth_signup_title: "Create your account", email: "Email", password: "Password",
  full_name: "Full name", forgot: "Forgot your password?", reset_sent: "We sent a password reset link to your email.",
  google: "Continue with Google", have_account: "Already have an account?", no_account: "New to EvalBot?",
  check_email: "Check your email and click the confirmation link, then sign in.",
  password_hint: "At least 8 characters.",
  accounts_soon: "Accounts are being set up. In the meantime you can analyze a recorded interview or practice single questions.",
  open_demo: "Open the analyzer",

  onboard_title: "How will you use EvalBot?", onboard_candidate: "Practice interviews",
  onboard_candidate_d: "Prepare for jobs in your track and track your progress.", onboard_recruiter: "Hire for my company",
  onboard_recruiter_d: "Create job interviews and review candidates.", company_name: "Company name", website: "Website",

  hello: "Hi {name}", dash_sub: "Ready for your next interview?", stat_interviews: "Interviews", stat_average: "Average score",
  stat_best: "Best score", stat_minutes: "Minutes spoken", progress_title: "Your scores over time", skills_title: "Strongest and weakest skills",
  recent: "Recent interviews", empty_dash: "You haven't done an interview yet. Your first one takes about ten minutes.",
  st_in_progress: "Not finished", st_processing: "Building report", st_completed: "Done", st_failed: "Failed",
  resume: "Continue", view_report: "View report", answered_n: "{a} of {b} answered", mock: "Practice", job: "Job interview",
  delete_confirm: "Delete this interview and its recordings?",

  new_title: "New practice interview", track: "Track", search_tracks: "Search tracks", level: "Level",
  lv_intern: "Internship", lv_junior: "Junior", lv_mid: "Mid-level", lv_senior: "Senior", lv_lead: "Lead / Manager",
  style: "Interview style", ty_mixed: "Mixed", ty_mixed_d: "Technical, behavioral and motivation questions.",
  ty_technical: "Technical", ty_technical_d: "Role knowledge, tools and trade-offs.", ty_behavioral: "Behavioral",
  ty_behavioral_d: "Past experiences, teamwork and conflict.", ty_hr: "HR / Fit", ty_hr_d: "Motivation, goals and culture fit.",
  ty_case: "Problem solving", ty_case_d: "Scenarios you reason through out loud.",
  count: "Number of questions", feedback_lang: "Feedback language", custom_role: "Specific job title",
  custom_role_ph: "e.g. Junior Data Engineer at a fintech", cv: "Your CV", cv_ph: "Paste your CV text so questions can refer to your experience.",
  jd: "Job description", jd_ph: "Paste a job posting to get questions tailored to it.", start: "Start interview",
  preparing: "Preparing your questions…", g_tech: "Technology", g_design: "Design", g_business: "Business", g_other: "Other",
  english: "English", arabic: "العربية",

  q_of: "Question {n} of {total}", followup: "Follow-up", listen_again: "Listen again", start_answer: "Start answering",
  stop_answer: "I'm done answering", recording: "Recording", time_left: "{t} left", uploading: "Saving your answer…",
  finish_now: "Finish and get my report", camera: "Camera", camera_on: "Turn camera on", camera_off: "Turn camera off",
  camera_hint: "Optional. Only numbers such as eye contact and smiling leave your device, never the video.",
  mic_error: "EvalBot needs your microphone. Allow microphone access in your browser, then try again.",
  get_ready: "Take a breath. Start answering when you're ready.", answers_saved: "{n} answers saved",
  building_title: "Building your report", building_sub: "EvalBot is listening back to your answers, scoring each one and writing your feedback. This takes about a minute.",
  interview_done: "That was the last question.", answer_recorded: "Answer saved", too_short: "That recording was very short. Record your answer again?",
  record_again: "Record again", use_it: "Keep it",

  overall: "Overall", content: "Content", delivery: "Delivery", calibrated_title: "How a panel of interviewers would likely rate you",
  calibrated_sub: "Your position among 138 real interviews, each rated by nine people. Reliability shows how closely EvalBot matched that panel on people it never saw; a single human rater scores about {h}.",
  reliability: "Reliability", pct: "Better than {p}% of interviews", per_question: "Question by question", your_answer: "Your answer",
  went_well: "What went well", improve: "What to improve", stronger: "A stronger answer", delivery_tip: "Delivery tip",
  summary: "Summary", strengths: "Strengths", weaknesses: "Areas to develop", learning_plan: "What to study next",
  next_steps: "Next steps", role_fit: "Role fit", download_pdf: "Download PDF report", presence: "Camera presence",
  eye_contact: "Looking at the camera", smile: "Smiling", face_visible: "Face in frame", not_answered: "Not answered",
  report_failed: "We couldn't build this report.", voice_title: "Your voice", speaking_rate: "Speaking pace",
  wps: "words per second", fillers: "Filler words", fluency: "Fluency", confidence: "Confidence", anxiety: "Nervousness",
  sig_strong_yes: "Strong hire", sig_yes: "Hire", sig_maybe: "Maybe", sig_no: "Not now", hiring_signal: "Hiring signal",
  practice_again: "Practice this track again", evidence: "Evidence",
  lv: { high: "High", moderate: "Moderate", low: "Low", fluent: "Fluent", disfluent: "Hesitant" } as Record<string, string>,

  jobs_title: "Jobs", new_job: "New job", empty_jobs: "Create your first job to get an interview link to share with applicants.",
  applicants: "Applicants", completed_n: "Completed", copy_link: "Copy interview link", link_copied: "Link copied",
  jst_open: "Open", jst_draft: "Draft", jst_closed: "Closed", job_title: "Job title", job_desc: "Description",
  answer_time: "Time per answer", questions: "Questions", add_question: "Add question", suggest: "Suggest questions with AI",
  suggesting: "Writing questions…", save_job: "Save job", job_status: "Status", question_ph: "Write a question",
  candidates_title: "Candidates, highest score first", empty_candidates: "No one has interviewed yet. Share the interview link with applicants.",
  c_name: "Candidate", c_score: "Score", c_signal: "EvalBot signal", c_status: "Your decision", c_date: "Date",
  rv_new: "New", rv_shortlisted: "Shortlisted", rv_rejected: "Rejected", rv_hired: "Hired", all: "All",
  decision: "Decision", rating: "Your rating", notes: "Notes for your team", save_review: "Save decision",
  fairness: "Scores support your judgment; they don't replace it. Listen to the answers before deciding.",
  share_hint: "Anyone with this link can take the interview after signing in.",

  apply_title: "{company} invited you to interview", apply_for: "for {title}", apply_q: "{n} questions",
  apply_time: "Up to {m} minutes per answer", apply_how: "You'll answer each question out loud. Find a quiet place and allow microphone access.",
  apply_start: "Start the interview", apply_signin: "Sign in to start", apply_closed: "This job isn't accepting interviews any more.",
  apply_done: "You've completed this interview. The hiring team will review it.",

  settings_title: "Settings", profile: "Profile", headline: "Headline", headline_ph: "e.g. Data engineering graduate",
  target_track: "Target track", new_password: "New password", change_password: "Change password", password_changed: "Password changed",
  company: "Company",
};

type Dict = typeof en;

const ar: Dict = {
  brand: "EvalBot",
  nav_dashboard: "الرئيسية", nav_new: "مقابلة جديدة", nav_history: "مقابلاتي", nav_jobs: "الوظائف",
  nav_settings: "الإعدادات", nav_quick: "تحليل تسجيل", sign_out: "تسجيل الخروج", sign_in: "تسجيل الدخول", sign_up: "إنشاء حساب",
  get_started: "ابدأ الآن", loading: "جارٍ التحميل…", save: "حفظ", saved: "تم الحفظ", cancel: "إلغاء", delete: "حذف",
  edit: "تعديل", back: "رجوع", continue: "متابعة", retry: "حاول مرة أخرى", copy: "نسخ", copied: "تم النسخ", theme_dark: "الوضع الداكن",
  theme_light: "الوضع الفاتح", language: "اللغة", min: "دقيقة", sec: "ثانية", of: "من", or: "أو", optional: "اختياري",
  error_generic: "حدث خطأ. حاول مرة أخرى بعد قليل.",

  hero_title: "تدرّب على المقابلة قبل المقابلة.",
  hero_sub: "يسألك EvalBot أسئلة حقيقية في مجالك، ويستمع إلى طريقة إجابتك، ويوضح لك بالضبط ما تحتاج إلى تحسينه. درجات الأداء فيه مدرّبة على تقييم لجان من المقيّمين لـ 138 مقابلة حقيقية.",
  cta_candidate: "ابدأ مقابلة تدريبية", cta_company: "وظّف باستخدام EvalBot",
  demo_asking: "EvalBot يسأل", demo_question: "Tell me about a data pipeline you built, and what broke first.",
  demo_listening: "يستمع", demo_you: "أنت", demo_answer: "We ingested sensor data through Kafka. The first thing that broke was…",
  demo_content: "المحتوى", demo_delivery: "الأداء", demo_structure: "التنظيم",
  for_candidates: "للباحثين عن عمل", for_companies: "لفرق التوظيف",
  c1_t: "أي مجال وأي مستوى", c1_d: "البيانات، والـ Backend، والتصميم، والمبيعات، والموارد البشرية و25 مجالاً آخر، من التدريب إلى القيادة. الصق وصف وظيفة أو سيرتك الذاتية وستُبنى الأسئلة عليها.",
  c2_t: "محادثة حقيقية", c2_d: "تُقرأ الأسئلة بصوت عالٍ وتجيب بصوتك. وإذا تركت إجابتك نقطة مفتوحة، يسألك EvalBot سؤال متابعة كما يفعل المحاوِر الحقيقي.",
  c3_t: "ملاحظات قابلة للتطبيق", c3_d: "كل إجابة تحصل على درجة، وما كان جيداً، وما يحتاج إلى تحسين، ونسخة أقوى من إجابتك مبنية على معلوماتك أنت.",
  c4_t: "شاهد تطوّرك", c4_d: "تُتابَع درجاتك وسرعة كلامك وكلمات الحشو عبر المقابلات، مع خطة تعلّم لمجالك.",
  r1_t: "رابط واحد", r1_d: "أنشئ وظيفة بأسئلتك أو بأسئلة يقترحها الذكاء الاصطناعي، وشارك رابطاً واحداً مع المتقدمين.",
  r2_t: "المقابلة نفسها للجميع", r2_d: "يجيب كل متقدم عن الأسئلة نفسها وبالوقت نفسه، في الوقت الذي يناسبه.",
  r3_t: "قائمة مرتّبة بالأسباب", r3_d: "يُرتَّب المرشحون حسب الدرجة، ومع كل منهم تقييم مكتوب والتسجيلات ونص المقابلة.",
  r4_t: "القرار لفريقك", r4_d: "رشّح أو ارفض، وقيّم، واترك ملاحظات. EvalBot يساعد في القرار، والقرار للبشر.",
  science_title: "تقييم يشبه لجنة من المحاورين",
  science_text: "درّبنا درجات الأداء في EvalBot على بيانات MIT Interview Dataset: ‏138 مقابلة تدريبية مسجّلة، قيّم كلاً منها تسعة أشخاص. وعند اختباره على أشخاص لم يرهم، يساوي EvalBot مقيّماً بشرياً واحداً أو يتفوق عليه في كلمات الحشو وتنظيم الإجابات والهدوء واستخدام التوقف، ويقترب منه في الحماس والتوصية بالتعيين.",
  science_model: "EvalBot", science_human: "مقيّم بشري واحد",
  science_note: "معامل الارتباط مع متوسط اللجنة، باختبار على أشخاص لم يرهم النموذج.",
  how_title: "كيف تتم المقابلة التدريبية",
  how_1: "اختر مجالك ومستواك ونوع المقابلة.", how_2: "أجب عن كل سؤال بصوتك، مع الكاميرا أو بدونها.",
  how_3: "احصل على تقرير كامل بعد دقيقة، بالعربية أو الإنجليزية.",
  tracks_title: "30 مجالاً مهنياً",
  footer_text: "بدأ EvalBot مشروعَ تخرج في كلية الحاسبات والذكاء الاصطناعي، جامعة بنها.",
  footer_privacy: "تسجيلاتك لا يراها غيرك، وفي مقابلات الوظائف تراها الشركة التي تقدمت إليها فقط.",

  auth_signin_title: "أهلاً بعودتك", auth_signup_title: "أنشئ حسابك", email: "البريد الإلكتروني", password: "كلمة المرور",
  full_name: "الاسم الكامل", forgot: "نسيت كلمة المرور؟", reset_sent: "أرسلنا رابط إعادة تعيين كلمة المرور إلى بريدك.",
  google: "المتابعة بحساب Google", have_account: "لديك حساب بالفعل؟", no_account: "جديد على EvalBot؟",
  check_email: "افتح بريدك واضغط رابط التأكيد، ثم سجّل الدخول.",
  password_hint: "8 أحرف على الأقل.",
  accounts_soon: "يتم تجهيز الحسابات حالياً. وفي الأثناء يمكنك تحليل مقابلة مسجّلة أو التدرّب على أسئلة منفردة.",
  open_demo: "افتح أداة التحليل",

  onboard_title: "كيف ستستخدم EvalBot؟", onboard_candidate: "أتدرّب على المقابلات",
  onboard_candidate_d: "استعد للوظائف في مجالك وتابع تطوّرك.", onboard_recruiter: "أوظّف لشركتي",
  onboard_recruiter_d: "أنشئ مقابلات للوظائف وراجع المرشحين.", company_name: "اسم الشركة", website: "الموقع الإلكتروني",

  hello: "أهلاً {name}", dash_sub: "جاهز لمقابلتك القادمة؟", stat_interviews: "المقابلات", stat_average: "متوسط الدرجة",
  stat_best: "أعلى درجة", stat_minutes: "دقائق الكلام", progress_title: "درجاتك عبر الوقت", skills_title: "أقوى مهاراتك وأضعفها",
  recent: "آخر المقابلات", empty_dash: "لم تُجرِ أي مقابلة بعد. أول مقابلة تستغرق نحو عشر دقائق.",
  st_in_progress: "لم تكتمل", st_processing: "جارٍ إعداد التقرير", st_completed: "مكتملة", st_failed: "فشلت",
  resume: "متابعة", view_report: "عرض التقرير", answered_n: "أُجيب عن {a} من {b}", mock: "تدريب", job: "مقابلة وظيفة",
  delete_confirm: "حذف هذه المقابلة وتسجيلاتها؟",

  new_title: "مقابلة تدريبية جديدة", track: "المجال", search_tracks: "ابحث عن مجال", level: "المستوى",
  lv_intern: "تدريب", lv_junior: "مبتدئ", lv_mid: "متوسط الخبرة", lv_senior: "خبير", lv_lead: "قائد فريق / مدير",
  style: "نوع المقابلة", ty_mixed: "متنوعة", ty_mixed_d: "أسئلة تقنية وسلوكية وعن الدافع.",
  ty_technical: "تقنية", ty_technical_d: "معرفة الدور والأدوات والمفاضلات.", ty_behavioral: "سلوكية",
  ty_behavioral_d: "تجاربك السابقة والعمل الجماعي والخلافات.", ty_hr: "موارد بشرية / ملاءمة", ty_hr_d: "الدافع والأهداف والملاءمة لثقافة الشركة.",
  ty_case: "حل مشكلات", ty_case_d: "مواقف تفكّر فيها بصوت عالٍ.",
  count: "عدد الأسئلة", feedback_lang: "لغة التقييم", custom_role: "مسمى وظيفي محدد",
  custom_role_ph: "مثال: Junior Data Engineer في شركة fintech", cv: "سيرتك الذاتية", cv_ph: "الصق نص سيرتك الذاتية لتشير الأسئلة إلى خبرتك.",
  jd: "وصف الوظيفة", jd_ph: "الصق إعلان وظيفة لتحصل على أسئلة مخصصة له.", start: "ابدأ المقابلة",
  preparing: "جارٍ إعداد أسئلتك…", g_tech: "التكنولوجيا", g_design: "التصميم", g_business: "الأعمال", g_other: "أخرى",
  english: "English", arabic: "العربية",

  q_of: "السؤال {n} من {total}", followup: "سؤال متابعة", listen_again: "استمع مرة أخرى", start_answer: "ابدأ الإجابة",
  stop_answer: "انتهيت من الإجابة", recording: "يسجّل", time_left: "متبقٍ {t}", uploading: "جارٍ حفظ إجابتك…",
  finish_now: "إنهاء والحصول على التقرير", camera: "الكاميرا", camera_on: "تشغيل الكاميرا", camera_off: "إيقاف الكاميرا",
  camera_hint: "اختياري. لا يخرج من جهازك إلا أرقام مثل التواصل البصري والابتسام، وليس الفيديو أبداً.",
  mic_error: "يحتاج EvalBot إلى الميكروفون. اسمح باستخدامه من المتصفح ثم حاول مرة أخرى.",
  get_ready: "خذ نفساً. ابدأ الإجابة عندما تكون جاهزاً.", answers_saved: "تم حفظ {n} إجابات",
  building_title: "جارٍ إعداد تقريرك", building_sub: "يستمع EvalBot إلى إجاباتك ويقيّم كل واحدة ويكتب ملاحظاتك. يستغرق هذا نحو دقيقة.",
  interview_done: "كان هذا آخر سؤال.", answer_recorded: "تم حفظ الإجابة", too_short: "التسجيل قصير جداً. هل تريد إعادة تسجيل إجابتك؟",
  record_again: "سجّل مرة أخرى", use_it: "احتفظ به",

  overall: "الإجمالي", content: "المحتوى", delivery: "الأداء", calibrated_title: "كيف ستقيّمك على الأرجح لجنة من المحاورين",
  calibrated_sub: "موقعك بين 138 مقابلة حقيقية قيّم كلاً منها تسعة أشخاص. ويوضح مقياس الموثوقية مدى اتفاق EvalBot مع اللجنة على أشخاص لم يرهم من قبل، ومقيّم بشري واحد يحقق نحو {h}.",
  reliability: "الموثوقية", pct: "أفضل من {p}% من المقابلات", per_question: "تقييم كل سؤال", your_answer: "إجابتك",
  went_well: "ما كان جيداً", improve: "ما يحتاج إلى تحسين", stronger: "إجابة أقوى", delivery_tip: "نصيحة للأداء",
  summary: "الملخص", strengths: "نقاط القوة", weaknesses: "مجالات التطوير", learning_plan: "ماذا تذاكر بعد ذلك",
  next_steps: "الخطوات التالية", role_fit: "الملاءمة للدور", download_pdf: "تحميل تقرير PDF", presence: "الحضور أمام الكاميرا",
  eye_contact: "النظر إلى الكاميرا", smile: "الابتسام", face_visible: "ظهور الوجه", not_answered: "لم تتم الإجابة",
  report_failed: "تعذّر إعداد هذا التقرير.", voice_title: "صوتك", speaking_rate: "سرعة الكلام",
  wps: "كلمة في الثانية", fillers: "كلمات الحشو", fluency: "الطلاقة", confidence: "الثقة", anxiety: "التوتر",
  sig_strong_yes: "تعيين بقوة", sig_yes: "تعيين", sig_maybe: "ربما", sig_no: "ليس الآن", hiring_signal: "مؤشر التوظيف",
  practice_again: "تدرّب على هذا المجال مرة أخرى", evidence: "الدليل",
  lv: { high: "مرتفع", moderate: "متوسط", low: "منخفض", fluent: "طليق", disfluent: "متردد" },

  jobs_title: "الوظائف", new_job: "وظيفة جديدة", empty_jobs: "أنشئ أول وظيفة لتحصل على رابط مقابلة تشاركه مع المتقدمين.",
  applicants: "المتقدمون", completed_n: "أكملوا", copy_link: "نسخ رابط المقابلة", link_copied: "تم نسخ الرابط",
  jst_open: "مفتوحة", jst_draft: "مسودة", jst_closed: "مغلقة", job_title: "المسمى الوظيفي", job_desc: "الوصف",
  answer_time: "الوقت المتاح لكل إجابة", questions: "الأسئلة", add_question: "إضافة سؤال", suggest: "اقترح أسئلة بالذكاء الاصطناعي",
  suggesting: "جارٍ كتابة الأسئلة…", save_job: "حفظ الوظيفة", job_status: "الحالة", question_ph: "اكتب سؤالاً",
  candidates_title: "المرشحون، الأعلى درجة أولاً", empty_candidates: "لم يُجرِ أحد المقابلة بعد. شارك رابط المقابلة مع المتقدمين.",
  c_name: "المرشح", c_score: "الدرجة", c_signal: "مؤشر EvalBot", c_status: "قرارك", c_date: "التاريخ",
  rv_new: "جديد", rv_shortlisted: "مرشّح", rv_rejected: "مرفوض", rv_hired: "تم تعيينه", all: "الكل",
  decision: "القرار", rating: "تقييمك", notes: "ملاحظات لفريقك", save_review: "حفظ القرار",
  fairness: "الدرجات تدعم حكمك ولا تحل محله. استمع إلى الإجابات قبل اتخاذ القرار.",
  share_hint: "يستطيع أي شخص لديه هذا الرابط إجراء المقابلة بعد تسجيل الدخول.",

  apply_title: "تدعوك {company} لإجراء مقابلة", apply_for: "لوظيفة {title}", apply_q: "{n} أسئلة",
  apply_time: "حتى {m} دقيقة لكل إجابة", apply_how: "ستجيب عن كل سؤال بصوتك. اختر مكاناً هادئاً واسمح باستخدام الميكروفون.",
  apply_start: "ابدأ المقابلة", apply_signin: "سجّل الدخول للبدء", apply_closed: "هذه الوظيفة لم تعد تستقبل مقابلات.",
  apply_done: "أكملت هذه المقابلة. سيراجعها فريق التوظيف.",

  settings_title: "الإعدادات", profile: "الملف الشخصي", headline: "نبذة قصيرة", headline_ph: "مثال: خريج هندسة بيانات",
  target_track: "المجال المستهدف", new_password: "كلمة مرور جديدة", change_password: "تغيير كلمة المرور", password_changed: "تم تغيير كلمة المرور",
  company: "الشركة",
};

export type Lang = "en" | "ar";
type I18n = { lang: Lang; dir: "ltr" | "rtl"; t: (k: keyof Dict, vars?: Record<string, string | number>) => string; d: Dict; setLang: (l: Lang) => void };
const Ctx = createContext<I18n | null>(null);

function initialLang(): Lang {
  try {
    const s = localStorage.getItem("evalbot_lang");
    if (s === "en" || s === "ar") return s;
  } catch {
    /* ignore */
  }
  return navigator.language?.startsWith("ar") ? "ar" : "en";
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(initialLang);
  const d = lang === "ar" ? ar : en;
  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
  }, [lang]);
  const setLang = (l: Lang) => {
    setLangState(l);
    try {
      localStorage.setItem("evalbot_lang", l);
    } catch {
      /* ignore */
    }
  };
  const t = (k: keyof Dict, vars?: Record<string, string | number>) => {
    let s = String(d[k] ?? en[k] ?? k);
    if (vars) for (const [vk, vv] of Object.entries(vars)) s = s.replace(`{${vk}}`, String(vv));
    return s;
  };
  return <Ctx.Provider value={{ lang, dir: lang === "ar" ? "rtl" : "ltr", t, d, setLang }}>{children}</Ctx.Provider>;
}

export function useI18n(): I18n {
  const v = useContext(Ctx);
  if (!v) throw new Error("useI18n outside provider");
  return v;
}

export function trackName(tracks: { id: string; en: string; ar: string }[] | undefined, id: string | null | undefined, lang: Lang) {
  const t = tracks?.find((x) => x.id === id);
  return t ? (lang === "ar" ? t.ar : t.en) : id || "";
}
