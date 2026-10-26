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
  auth_signin_sub: "Sign in to continue to your interviews or your hiring dashboard.",
  auth_signup_sub: "Free to use. It takes less than a minute.", auth_tabs: "Sign in or create an account",
  account_type: "I'm joining as", kind_candidate: "Job seeker", kind_candidate_d: "Practice, find jobs and apply",
  kind_company: "Company", kind_company_d: "Post jobs and review candidates", your_name: "Your name", work_email: "Work email",
  create_company_account: "Create company account", forgot_need_email: "Enter your email first, then tap “Forgot your password?”.",
  show_password: "Show password", hide_password: "Hide password",
  side_title: "Interviews that tell you exactly what to improve.",
  side_p1: "Spoken mock interviews for 30 career tracks, with follow-up questions like a real interviewer.",
  side_p2: "A score and a stronger version of every answer, in English or Arabic.",
  side_p3: "Delivery scores trained on how human panels rated 138 real interviews.",
  side_title_c: "Hire faster, with the same fair interview for everyone.",
  side_c1: "Post a job and share one link. Candidates interview whenever it suits them.",
  side_c2: "A ranked shortlist with scores, recordings, transcripts and a written assessment.",
  side_c3: "A hiring dashboard: funnel, score distribution, top 10 candidates and CSV export.",

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

  nav_board: "Find jobs", nav_applications: "My applications", nav_overview: "Overview", nav_practice: "Practice",
  browse_jobs: "Browse jobs",
  board_title: "Find your next job", board_sub: "Open roles from companies hiring with EvalBot. Each one starts with a short spoken interview you can take whenever it suits you.",
  board_search: "Search by title, skill, company or city", any_track: "Any track", any_level: "Any level", any_mode: "Any work mode",
  any_type: "Any job type", empty_board: "No open jobs match your search right now. Try fewer filters, or practice for your track meanwhile.",
  wm_onsite: "On-site", wm_remote: "Remote", wm_hybrid: "Hybrid",
  et_full_time: "Full-time", et_part_time: "Part-time", et_internship: "Internship", et_contract: "Contract",
  applied: "Applied", view_job: "View job", posted: "Posted {d}", deadline: "Apply by {d}", n_applicants: "{n} applicants",
  open_roles: "Open roles", see_all_jobs: "See all jobs",
  apps_title: "My applications", apps_empty: "You haven't applied to a job yet.", app_status: "Application status",
  as_new: "Under review", as_shortlisted: "Shortlisted", as_rejected: "Not selected", as_hired: "Offer stage",
  as_unfinished: "Interview not finished", as_processing: "Interview being scored", finish_interview: "Finish interview",
  company_cant_apply: "You're signed in with a company account. Use a personal account to apply to jobs.",
  about_company: "About {company}", skills_req: "Skills", salary: "Salary", location: "Location", work_mode: "Work mode",
  employment_type: "Job type", visibility: "Who can see it", vis_public: "Public: listed on the EvalBot job board",
  vis_link: "Private: only people with the link", skills_ph: "Python, SQL, Spark", salary_ph: "e.g. EGP 25k-35k / month",
  location_ph: "e.g. Cairo, Egypt", deadline_l: "Application deadline", job_basics: "Job post", job_interview: "Interview",
  industry: "Industry", company_size: "Company size", company_about: "About the company", company_loc: "Headquarters",

  co_hello: "{company} hiring overview", co_sub: "Every number below updates as candidates finish their interviews.",
  k_open_jobs: "Open jobs", k_applicants: "Applicants", k_completed: "Interviews completed", k_avg: "Average score",
  k_to_review: "Waiting for your review", k_shortlisted: "Shortlisted", k_hired: "Hired", k_completion: "Completion rate",
  k_views: "Job views", k_median: "Median score", k_best: "Best score", k_minutes: "Avg. interview length",
  funnel_title: "Hiring funnel", fn_views: "Viewed the job", fn_started: "Started the interview", fn_completed: "Completed",
  fn_shortlisted: "Shortlisted", fn_hired: "Hired",
  timeline_title: "Applications in the last 30 days", dist_title: "Score distribution", signals_title: "EvalBot hiring signal",
  top_title: "Top 10 candidates", traits_title: "Candidate pool: delivery profile",
  traits_sub: "Average position of your candidates among the 138 human-rated reference interviews.",
  skills_pool: "Skills across all answers", jobs_table: "Jobs at a glance", export_csv: "Export CSV", c_job: "Job",
  empty_company: "Post your first job to start receiving interviews. Public jobs appear on the EvalBot job board, and every job gets a link you can share anywhere.",
  job_stats: "This job in numbers", search_candidates: "Search candidates", min_score: "Minimum score",
  co_new_job_cta: "Post a job", out_of_100: "out of 100", delete_job: "Delete job",
  delete_job_confirm: "Delete this job and all of its interviews? This can't be undone. To stop new applications but keep the results, set the status to Closed instead.",
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
  auth_signin_sub: "سجّل الدخول لتكمل مقابلاتك أو لوحة التوظيف الخاصة بشركتك.",
  auth_signup_sub: "مجاني، ويستغرق أقل من دقيقة.", auth_tabs: "تسجيل الدخول أو إنشاء حساب",
  account_type: "أنضم بصفتي", kind_candidate: "باحث عن عمل", kind_candidate_d: "أتدرّب وأبحث عن وظائف وأتقدّم",
  kind_company: "شركة", kind_company_d: "أنشر وظائف وأراجع المرشحين", your_name: "اسمك", work_email: "بريد العمل",
  create_company_account: "إنشاء حساب الشركة", forgot_need_email: "اكتب بريدك أولاً، ثم اضغط «نسيت كلمة المرور؟».",
  show_password: "إظهار كلمة المرور", hide_password: "إخفاء كلمة المرور",
  side_title: "مقابلات توضّح لك بالضبط ما تحتاج إلى تحسينه.",
  side_p1: "مقابلات تدريبية صوتية في 30 مجالاً، مع أسئلة متابعة كما يفعل المحاوِر الحقيقي.",
  side_p2: "درجة ونسخة أقوى من كل إجابة، بالعربية أو الإنجليزية.",
  side_p3: "درجات الأداء مدرّبة على تقييم لجان بشرية لـ 138 مقابلة حقيقية.",
  side_title_c: "وظّف أسرع، بمقابلة واحدة عادلة للجميع.",
  side_c1: "انشر الوظيفة وشارك رابطاً واحداً، ويجري المرشحون المقابلة في الوقت المناسب لهم.",
  side_c2: "قائمة مرتّبة بالدرجات والتسجيلات ونصوص الإجابات وتقييم مكتوب.",
  side_c3: "لوحة توظيف: مسار التقديم، وتوزيع الدرجات، وأفضل 10 مرشحين، وتصدير CSV.",

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

  nav_board: "ابحث عن وظيفة", nav_applications: "طلباتي", nav_overview: "نظرة عامة", nav_practice: "تدريب",
  browse_jobs: "تصفّح الوظائف",
  board_title: "ابحث عن وظيفتك القادمة", board_sub: "وظائف مفتوحة من شركات توظّف باستخدام EvalBot. كل وظيفة تبدأ بمقابلة صوتية قصيرة تجريها في الوقت الذي يناسبك.",
  board_search: "ابحث بالمسمى أو المهارة أو الشركة أو المدينة", any_track: "كل المجالات", any_level: "كل المستويات", any_mode: "كل أنماط العمل",
  any_type: "كل أنواع الوظائف", empty_board: "لا توجد وظائف مفتوحة تطابق بحثك الآن. جرّب فلاتر أقل، أو تدرّب على مجالك في الأثناء.",
  wm_onsite: "من المقر", wm_remote: "عن بُعد", wm_hybrid: "هجين",
  et_full_time: "دوام كامل", et_part_time: "دوام جزئي", et_internship: "تدريب", et_contract: "عقد مؤقت",
  applied: "تقدّمت", view_job: "عرض الوظيفة", posted: "نُشرت {d}", deadline: "التقديم حتى {d}", n_applicants: "{n} متقدم",
  open_roles: "وظائف مفتوحة", see_all_jobs: "كل الوظائف",
  apps_title: "طلباتي", apps_empty: "لم تتقدم إلى أي وظيفة بعد.", app_status: "حالة الطلب",
  as_new: "قيد المراجعة", as_shortlisted: "في القائمة المختصرة", as_rejected: "لم يتم الاختيار", as_hired: "مرحلة العرض الوظيفي",
  as_unfinished: "المقابلة لم تكتمل", as_processing: "جارٍ تقييم المقابلة", finish_interview: "أكمل المقابلة",
  company_cant_apply: "أنت مسجّل بحساب شركة. استخدم حساباً شخصياً للتقدم إلى الوظائف.",
  about_company: "عن {company}", skills_req: "المهارات", salary: "الراتب", location: "المكان", work_mode: "نمط العمل",
  employment_type: "نوع الوظيفة", visibility: "من يستطيع رؤيتها", vis_public: "عامة: تظهر في لوحة وظائف EvalBot",
  vis_link: "خاصة: لمن لديه الرابط فقط", skills_ph: "Python, SQL, Spark", salary_ph: "مثال: 25-35 ألف جنيه شهرياً",
  location_ph: "مثال: القاهرة، مصر", deadline_l: "آخر موعد للتقديم", job_basics: "إعلان الوظيفة", job_interview: "المقابلة",
  industry: "القطاع", company_size: "حجم الشركة", company_about: "عن الشركة", company_loc: "المقر الرئيسي",

  co_hello: "نظرة على التوظيف في {company}", co_sub: "كل الأرقام هنا تتحدّث تلقائياً كلما أنهى مرشح مقابلته.",
  k_open_jobs: "وظائف مفتوحة", k_applicants: "المتقدمون", k_completed: "مقابلات مكتملة", k_avg: "متوسط الدرجة",
  k_to_review: "بانتظار مراجعتك", k_shortlisted: "في القائمة المختصرة", k_hired: "تم تعيينهم", k_completion: "نسبة الإكمال",
  k_views: "مشاهدات الوظائف", k_median: "الدرجة الوسيطة", k_best: "أعلى درجة", k_minutes: "متوسط مدة المقابلة",
  funnel_title: "مسار التوظيف", fn_views: "شاهدوا الوظيفة", fn_started: "بدأوا المقابلة", fn_completed: "أكملوها",
  fn_shortlisted: "في القائمة المختصرة", fn_hired: "تم تعيينهم",
  timeline_title: "الطلبات في آخر 30 يوماً", dist_title: "توزيع الدرجات", signals_title: "مؤشر التوظيف من EvalBot",
  top_title: "أفضل 10 مرشحين", traits_title: "المرشحون: ملف الأداء",
  traits_sub: "متوسط موقع مرشحيك بين 138 مقابلة مرجعية قيّمها بشر.",
  skills_pool: "المهارات عبر كل الإجابات", jobs_table: "الوظائف باختصار", export_csv: "تصدير CSV", c_job: "الوظيفة",
  empty_company: "انشر أول وظيفة لتبدأ في استقبال المقابلات. الوظائف العامة تظهر في لوحة وظائف EvalBot، ولكل وظيفة رابط تشاركه في أي مكان.",
  job_stats: "الوظيفة بالأرقام", search_candidates: "ابحث في المرشحين", min_score: "أقل درجة",
  co_new_job_cta: "انشر وظيفة", out_of_100: "من 100", delete_job: "حذف الوظيفة",
  delete_job_confirm: "حذف هذه الوظيفة وكل مقابلاتها؟ لا يمكن التراجع عن ذلك. لإيقاف التقديم مع الاحتفاظ بالنتائج، اجعل الحالة «مغلقة» بدلاً من الحذف.",
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
