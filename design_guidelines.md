{
  "meta": {
    "product": "ManuelIA v2",
    "style_goal": "Reproduce the provided manuelia-v2.html visual system faithfully in React + Tailwind, with CSS-in-CSS (App.css) using the exact CSS variables and typography.",
    "theme": "dark-only",
    "accent": "violet",
    "language": "fr-FR",
    "tech": {
      "frontend": "React 19 (JS files), react-router-dom 7, Tailwind 3.4, framer-motion, sonner",
      "backend": "FastAPI",
      "notes": [
        "Chrome (app shell) is custom CSS (NOT shadcn).",
        "Shadcn/ui may be used for form primitives only (Input, Label, Button, Textarea, Switch, Dialog, Sheet, ScrollArea, Skeleton, Progress).",
        "All interactive + key informational elements MUST include data-testid attributes (kebab-case)."
      ]
    },
    "reference_html": {
      "url": "https://customer-assets.emergentagent.com/job_9a7718b9-c5ff-4efa-8652-0b5268eebd94/artifacts/f5yo1vxx_manuelia-v2.html",
      "must_match": [
        "palette",
        "typography",
        "spacing",
        "glass cards",
        "sidebar width 232px",
        "topbar height 58px",
        "noise overlay + violet blobs",
        "badge with green dot + glow",
        "compact class naming acceptable"
      ]
    }
  },

  "design_tokens": {
    "google_fonts_import": "@import url('https://fonts.googleapis.com/css2?family=Syne:wght@600;700;800&family=DM+Sans:wght@300;400;500&family=JetBrains+Mono:wght@400;500&display=swap');",

    "css_variables_block": ":root {\n  --bg: #0e0d13;\n  --surface: #16141e;\n  --surface2: #1e1b2a;\n  --surface3: #252235;\n\n  --border: #2e2940;\n  --border2: #3d3757;\n\n  --violet: #7c5cbf;\n  --violet-light: #9d7de0;\n  --violet-bright: #b49af0;\n  --mauve: #d4bef5;\n\n  --text: #f0ecff;\n  --text2: #b8b3d0;\n  --text3: #7a758f;\n\n  --success: #6bcba0;\n  --warning: #e8b86d;\n  --danger: #e87d7d;\n\n  /* layout */\n  --sidebar-w: 232px;\n  --topbar-h: 58px;\n  --radius-sm: 8px;\n  --radius-xs: 6px;\n\n  /* shadows/glow */\n  --shadow-1: 0 10px 30px rgba(0,0,0,.35);\n  --shadow-2: 0 14px 50px rgba(0,0,0,.45);\n  --glow-violet: 0 0 0 1px rgba(124,92,191,.35), 0 0 24px rgba(124,92,191,.18);\n  --glow-success: 0 0 0 1px rgba(107,203,160,.35), 0 0 18px rgba(107,203,160,.18);\n\n  /* typography */\n  --font-title: 'Syne', system-ui, -apple-system, Segoe UI, Roboto, sans-serif;\n  --font-body: 'DM Sans', system-ui, -apple-system, Segoe UI, Roboto, sans-serif;\n  --font-mono: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;\n\n  /* focus */\n  --ring: 0 0 0 3px rgba(124,92,191,.35);\n}\n",

    "typography": {
      "titles": {
        "font": "var(--font-title)",
        "weights": [600, 700, 800],
        "usage": ["page titles", "card titles", "section headers", "wizard step labels"]
      },
      "body": {
        "font": "var(--font-body)",
        "weights": [300, 400, 500],
        "usage": ["paragraphs", "labels", "helper text", "buttons"]
      },
      "mono": {
        "font": "var(--font-mono)",
        "weights": [400, 500],
        "usage": ["numbers", "badges", "step counters", "status labels", "credit pack quantities"]
      },
      "scale": {
        "h1": "text-4xl sm:text-5xl lg:text-6xl (Syne 800)",
        "h2_subtitle": "text-base md:text-lg (DM Sans 400, color var(--text2))",
        "body": "text-sm md:text-base (DM Sans 400)",
        "small": "text-xs text-[color:var(--text3)]",
        "mono_small": "text-xs font-mono tracking-tight"
      },
      "letter_spacing": {
        "titles": "tracking-[-0.02em]",
        "mono": "tracking-[-0.01em]"
      }
    },

    "spacing": {
      "content_padding": "24px desktop, 16px mobile",
      "card_padding": "16px-18px",
      "stack_gaps": "gap-10 for major sections, gap-6 for sub-sections, gap-3 for dense rows",
      "rule": "Prefer 2–3x more spacing than default; keep reading areas calm."
    },

    "radius": {
      "cards": "var(--radius-sm) ~ 8px",
      "buttons": "var(--radius-xs) 6px",
      "chips": "999px (pill)",
      "inputs": "8px"
    }
  },

  "global_css_and_resets": {
    "where": "/app/frontend/src/App.css (replace CRA demo styles)",
    "instructions": [
      "Import Google Fonts at the top of App.css.",
      "Set html/body height:100%; background: var(--bg); color: var(--text); font-family: var(--font-body).",
      "Remove any centered .App defaults; do NOT add text-align:center.",
      "Set selection colors: background rgba(124,92,191,.35), color var(--text).",
      "Define focus-visible ring using --ring; ensure keyboard nav is obvious.",
      "Do NOT use transition: all anywhere."
    ],
    "base_rules_snippet": "html, body, #root { height: 100%; }\nbody { margin: 0; background: var(--bg); color: var(--text); font-family: var(--font-body); -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; }\n* { box-sizing: border-box; }\n::selection { background: rgba(124,92,191,.35); color: var(--text); }\n:focus-visible { outline: none; box-shadow: var(--ring); border-radius: 6px; }\n"
  },

  "background_effects": {
    "noise_overlay": {
      "requirement": "Subtle SVG feTurbulence noise overlay opacity 0.04 across the whole app.",
      "implementation": {
        "pattern": "Use a fixed-position pseudo-element on .bg (or body::before) with pointer-events:none.",
        "css": ".bg-noise::before { content:''; position: fixed; inset: 0; pointer-events: none; opacity: .04; background-image: url('data:image/svg+xml;utf8,<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"160\" height=\"160\"><filter id=\"n\"><feTurbulence type=\"fractalNoise\" baseFrequency=\"0.8\" numOctaves=\"3\" stitchTiles=\"stitch\"/></filter><rect width=\"160\" height=\"160\" filter=\"url(%23n)\" opacity=\"1\"/></svg>'); mix-blend-mode: overlay; }"
      }
    },
    "violet_blobs": {
      "requirement": "Two fixed-position violet light blobs (top-right and bottom-left) with blur(100px).",
      "implementation": {
        "css": ".bg-blobs::after, .bg-blobs::before { content:''; position: fixed; width: 520px; height: 520px; border-radius: 999px; filter: blur(100px); opacity: .22; pointer-events:none; }\n.bg-blobs::before { left: -180px; bottom: -220px; background: rgba(124,92,191,.55); }\n.bg-blobs::after { right: -220px; top: -220px; background: rgba(180,154,240,.55); }"
      },
      "rule": "Keep blobs behind content (z-index:-1 or on a wrapper with isolation)."
    }
  },

  "layout_primitives": {
    "app_shell": {
      "structure": "<div className='app bg-noise bg-blobs'> <aside className='sb'>…</aside> <main className='mn'> <header className='tb'>…</header> <div className='ct'>…</div> </main> </div>",
      "css": {
        ".app": "display:flex; min-height:100%; background: var(--bg);",
        ".sb": "width: var(--sidebar-w); flex: 0 0 var(--sidebar-w); position: sticky; top: 0; height: 100vh; padding: 18px 14px; border-right: 1px solid var(--border); background: rgba(22,20,30,.72); backdrop-filter: blur(10px);",
        ".mn": "flex:1; min-width:0; display:flex; flex-direction:column;",
        ".tb": "height: var(--topbar-h); flex: 0 0 var(--topbar-h); display:flex; align-items:center; justify-content:space-between; padding: 0 22px; border-bottom: 1px solid var(--border); background: rgba(14,13,19,.55); backdrop-filter: blur(10px);",
        ".ct": "flex:1; min-height:0; overflow:auto; padding: 24px;"
      },
      "responsive": {
        "tablet": "At <=1024px allow sidebar collapse into Sheet (shadcn Sheet) triggered by hamburger in topbar.",
        "mobile": "Content padding 16px; topbar remains 58px; sidebar becomes overlay sheet."
      }
    },

    "public_share_shell": {
      "rule": "NO sidebar, NO topbar, NO editing actions. Full-screen reader view.",
      "structure": "<div className='share bg-noise bg-blobs'><div className='shareWrap'>…viewer…</div></div>",
      "css": {
        ".share": "min-height:100%; padding: 24px 16px;",
        ".shareWrap": "max-width: 1100px; margin: 0 auto;"
      }
    }
  },

  "component_patterns": {
    "cards": {
      "glass_card": {
        "class": "gc",
        "css": ".gc { background: rgba(22,20,30,.72); border: 1px solid rgba(61,55,87,.55); border-radius: var(--radius-sm); box-shadow: var(--shadow-1); backdrop-filter: blur(10px); }\n.gc--hi { box-shadow: var(--shadow-1), var(--glow-violet); border-color: rgba(124,92,191,.35); }",
        "hover": "On hover: border-color rgba(124,92,191,.55) + subtle lift translateY(-1px) (transition only box-shadow, border-color, background-color).",
        "tailwind_usage": "Use Tailwind for layout/spacing; keep the visual surface in App.css classes to match reference."
      },
      "stat_card": {
        "structure": "icon (left) + big number (mono) + label + delta",
        "number_style": "font-family var(--font-mono); font-weight:500; color var(--text); font-size ~28-32px",
        "delta": "text-xs color var(--text3) with green/up arrow or neutral"
      }
    },

    "buttons": {
      "base": {
        "class": "btn",
        "css": ".btn { display:inline-flex; align-items:center; justify-content:center; gap:8px; height: 36px; padding: 0 12px; border-radius: var(--radius-xs); font: 500 14px/1 var(--font-body); border: 1px solid transparent; cursor:pointer; user-select:none; }\n.btn:active { transform: translateY(1px); }",
        "focus": ".btn:focus-visible { box-shadow: var(--ring); }"
      },
      "primary": {
        "class": "btn btn--p",
        "css": ".btn--p { background: var(--violet); color: var(--text); border-color: rgba(180,154,240,.25); box-shadow: 0 10px 24px rgba(124,92,191,.18); }\n.btn--p:hover { background: var(--violet-light); }",
        "usage": ["✦ Nouveau", "Générer le manuel", "S'abonner", "↺ Régénérer"]
      },
      "ghost": {
        "class": "btn btn--g",
        "css": ".btn--g { background: rgba(30,27,42,.35); color: var(--text2); border-color: rgba(46,41,64,.9); }\n.btn--g:hover { background: rgba(37,34,53,.55); color: var(--text); border-color: rgba(124,92,191,.35); }"
      },
      "danger": {
        "class": "btn btn--d",
        "css": ".btn--d { background: rgba(232,125,125,.12); color: #ffdede; border-color: rgba(232,125,125,.35); }\n.btn--d:hover { background: rgba(232,125,125,.18); }"
      },
      "small_icon": {
        "class": "btn btn--ic",
        "css": ".btn--ic { width: 34px; padding: 0; }",
        "usage": ["viewer toolbar icons: share/export/regenerate"]
      }
    },

    "badges": {
      "model_badge": {
        "requirement": "Topbar badge: '● GPT-4o + DALL-E 3' with green dot #6bcba0 + glow.",
        "class": "bp",
        "css": ".bp { display:inline-flex; align-items:center; gap:8px; padding: 6px 10px; border-radius: 999px; background: rgba(22,20,30,.65); border: 1px solid rgba(46,41,64,.9); color: var(--text2); font: 500 12px/1 var(--font-mono); }\n.bp i, .bp .dot { width: 8px; height: 8px; border-radius: 999px; background: var(--success); box-shadow: 0 0 0 3px rgba(107,203,160,.12), 0 0 18px rgba(107,203,160,.25); }"
      },
      "status_badge": {
        "usage": ["Complet", "Brouillon", "Recommandé"],
        "css": ".bdg { display:inline-flex; align-items:center; padding: 4px 8px; border-radius: 999px; font: 500 12px/1 var(--font-mono); border: 1px solid rgba(46,41,64,.9); background: rgba(30,27,42,.35); color: var(--text2); }\n.bdg--ok { border-color: rgba(107,203,160,.35); color: #c9ffe9; }\n.bdg--warn { border-color: rgba(232,184,109,.35); color: #ffe7c2; }\n.bdg--violet { border-color: rgba(124,92,191,.35); color: var(--mauve); }"
      }
    },

    "inputs": {
      "text_input": {
        "class": "in",
        "css": ".in { width:100%; height: 40px; padding: 0 12px; border-radius: 8px; background: rgba(30,27,42,.35); border: 1px solid rgba(46,41,64,.9); color: var(--text); }\n.in::placeholder { color: rgba(184,179,208,.55); }\n.in:focus { outline:none; border-color: rgba(124,92,191,.55); box-shadow: var(--ring); }"
      },
      "textarea": {
        "class": "ta",
        "css": ".ta { width:100%; min-height: 92px; padding: 10px 12px; border-radius: 8px; background: rgba(30,27,42,.35); border: 1px solid rgba(46,41,64,.9); color: var(--text); resize: vertical; }"
      },
      "toggle_switch": {
        "component_path": "/app/frontend/src/components/ui/switch.jsx",
        "styling": "Wrap in a row with label/value; keep switch track tinted violet on checked (override via className + CSS vars)."
      }
    },

    "chips": {
      "suggestion_chip": {
        "class": "chip",
        "css": ".chip { display:inline-flex; align-items:center; height: 28px; padding: 0 10px; border-radius: 999px; background: rgba(30,27,42,.35); border: 1px solid rgba(46,41,64,.9); color: var(--text2); font: 500 12px/1 var(--font-mono); }\n.chip:hover { border-color: rgba(124,92,191,.45); color: var(--text); }\n.chip:active { transform: translateY(1px); }"
      }
    },

    "callouts": {
      "tip_callout": {
        "usage": "Manual step tip: '**Conseil GPT-4o** …'",
        "css": ".call { padding: 12px 12px; border-radius: 10px; background: rgba(124,92,191,.10); border: 1px solid rgba(124,92,191,.25); color: var(--text2); }\n.call strong { color: var(--mauve); }"
      },
      "success_callout": {
        "usage": "Settings: context partagé confirmation row",
        "css": ".call--ok { background: rgba(107,203,160,.10); border-color: rgba(107,203,160,.25); color: #d9fff0; }"
      }
    },

    "stepper_and_progress": {
      "wizard_stepper": {
        "structure": "Horizontal row of 4 steps with numbered circles; active step highlighted violet; completed shows ✓.",
        "css": ".stp { display:flex; gap: 10px; align-items:center; }\n.stpIt { display:flex; align-items:center; gap: 10px; padding: 10px 12px; border-radius: 12px; border: 1px solid rgba(46,41,64,.9); background: rgba(22,20,30,.55); }\n.stpNum { width: 26px; height: 26px; border-radius: 999px; display:grid; place-items:center; font: 500 12px/1 var(--font-mono); background: rgba(30,27,42,.55); border: 1px solid rgba(46,41,64,.9); color: var(--text2); }\n.stpIt--a { border-color: rgba(124,92,191,.45); box-shadow: var(--glow-violet); }\n.stpIt--a .stpNum { background: rgba(124,92,191,.22); border-color: rgba(124,92,191,.45); color: var(--mauve); }\n.stpLbl { font: 700 13px/1 var(--font-title); color: var(--text); }",
        "responsive": "On mobile, allow horizontal scroll (overflow-x:auto) with fade edges."
      },
      "progress_bar": {
        "usage": "Generation screen + regen-all overlay",
        "css": ".pr { height: 10px; border-radius: 999px; background: rgba(30,27,42,.55); border: 1px solid rgba(46,41,64,.9); overflow:hidden; }\n.pr > span { display:block; height:100%; width: var(--p, 0%); background: rgba(124,92,191,.85); box-shadow: 0 0 18px rgba(124,92,191,.25); transition: width 400ms ease; }",
        "label": "Small monospace label above: font-mono text-xs color var(--text3)"
      },
      "spinner": {
        "css": ".sp { width: 54px; height: 54px; border-radius: 999px; border: 3px solid rgba(46,41,64,.9); border-top-color: rgba(180,154,240,.9); animation: spin 900ms linear infinite; }\n@keyframes spin { to { transform: rotate(360deg); } }"
      }
    },

    "toasts": {
      "library": "sonner",
      "component_path": "/app/frontend/src/components/ui/sonner.jsx",
      "requirement": "Bottom-right stacked; dark cards with violet/green/red left border depending on type.",
      "styling": {
        "css": ".toast { background: rgba(22,20,30,.92); border: 1px solid rgba(46,41,64,.9); border-left-width: 3px; border-radius: 12px; color: var(--text); box-shadow: var(--shadow-2); }\n.toast--ok { border-left-color: var(--success); }\n.toast--err { border-left-color: var(--danger); }\n.toast--info { border-left-color: var(--violet); }",
        "motion": "Slide-in from bottom with slight blur; respect prefers-reduced-motion."
      },
      "copy_share_toast": "On share copy: show success toast text 'Lien copié !'"
    }
  },

  "page_wireframes": {
    "auth": {
      "route": "/auth",
      "chrome": "NO sidebar/topbar",
      "layout": {
        "structure": "Full-screen centered card",
        "classes": ["auth", "authCard gc gc--hi"],
        "css_notes": "Add violet glow behind card (pseudo-element radial gradient) but keep within 20% viewport (small halo only)."
      },
      "content": [
        "Logo/title 'ManuelIA' (Syne 800)",
        "Subtitle: 'Manuels illustrés étape par étape. Texte ET images générés par GPT-4o.'",
        "Email + password inputs",
        "Primary button 'Connexion'",
        "Divider 'ou'",
        "Ghost button 'Continuer avec Google'",
        "Footer link 'Créer un compte gratuit'"
      ],
      "data_testids": [
        "auth-email-input",
        "auth-password-input",
        "auth-submit-button",
        "auth-google-button",
        "auth-toggle-mode-link"
      ]
    },

    "dashboard": {
      "route": "/",
      "topbar": {
        "left": "Title 'Tableau de bord' + subtitle 'Bienvenue, {name}'",
        "right": "Model badge + primary button '✦ Nouveau'"
      },
      "content_layout": {
        "section_1": "3 stat cards in a 3-col grid (gap 14-16px). On tablet -> 2 cols; mobile -> 1 col.",
        "section_2": "Recent manuals header row (title + 'Voir tout' ghost link/button) then grid of manual cards + one 'Nouveau manuel' card.",
        "manual_card": "Status badge (Complet/Brouillon), title, meta '6 étapes · Intermédiaire', actions row (PDF, Partager, Continuer)."
      },
      "data_testids": [
        "dashboard-new-manual-button",
        "dashboard-stat-manuals-created",
        "dashboard-stat-images-generated",
        "dashboard-stat-pdfs-exported",
        "dashboard-recent-manual-card",
        "dashboard-new-manual-card"
      ]
    },

    "create_wizard": {
      "route": "/create",
      "layout": "Top: stepper. Below: step content card.",
      "steps": [
        "1 Projet: project name, description, difficulty, step count target",
        "2 Clarification: chat UI",
        "3 Génération: progress screen",
        "4 Révision: viewer-like review + export/share"
      ],
      "nav": "Bottom row: '← Retour' ghost + 'Générer le manuel →' primary (or next).",
      "data_testids": [
        "wizard-stepper",
        "wizard-back-button",
        "wizard-next-button"
      ]
    },

    "clarification_chat": {
      "within": "/create step 2",
      "layout": "Card with intro text + model callout + message list + composer",
      "message_bubbles": {
        "ai": "Avatar circle 'G' with subtle violet gradient; bubble surface2;",
        "user": "Avatar circle 'O' neutral; bubble surface;",
        "css": ".msg { display:flex; gap: 10px; }\n.av { width: 34px; height: 34px; border-radius: 999px; display:grid; place-items:center; font: 700 12px/1 var(--font-mono); }\n.av--ai { background: radial-gradient(circle at 30% 30%, rgba(180,154,240,.9), rgba(124,92,191,.55)); color: #120f1c; }\n.av--u { background: rgba(30,27,42,.65); border: 1px solid rgba(46,41,64,.9); color: var(--text2); }\n.bub { padding: 10px 12px; border-radius: 12px; border: 1px solid rgba(46,41,64,.9); background: rgba(30,27,42,.35); color: var(--text2); }\n.bub strong { color: var(--text); }"
      },
      "composer": "Textarea (ta) + Send primary button aligned right.",
      "data_testids": [
        "clarification-message-list",
        "clarification-textarea",
        "clarification-send-button"
      ]
    },

    "generation_progress": {
      "within": "/create step 3 and regen-all overlay",
      "layout": "Centered stack: spinner, title, status line, progress bar, mono step label.",
      "status_text_examples": [
        "GPT-4o analyse le contexte du chat…",
        "Rédaction étape 1…",
        "Génération image étape 1…"
      ],
      "data_testids": [
        "generation-spinner",
        "generation-status-text",
        "generation-progress-bar"
      ]
    },

    "manual_viewer": {
      "route": "/manual/:id",
      "topbar": {
        "left": "Title + meta '· 6 étapes · GPT-4o'",
        "right": "Buttons: '↺ Régénérer tout' (ghost), 'Partager' (ghost), 'Exporter PDF' (ghost)"
      },
      "layout": {
        "grid": "Two columns: left steps list (fixed ~280px) + right content (fluid).",
        "left": "Steps card with header 'Étapes du manuel' and list items with number + title + ✓ markers.",
        "right": "Step header (Étape X / N), title, meta (difficulty + time), image block, regen panel, instructions text, tip callout, prev/next nav."
      },
      "image_block": {
        "container": "Aspect ratio ~16:9 or 4:3; background surface2; border border;",
        "actions": "Small icon buttons overlay top-right: ↺ and ⬇",
        "skeleton": "Use shadcn Skeleton with custom bg rgba(30,27,42,.55)"
      },
      "regen_panel": {
        "default": "Collapsed row 'Instructions à GPT-4o (optionnel)' with chevron;",
        "expanded": "Textarea + chips row + primary '↺ Régénérer' button.",
        "chips": ["vue de dessus", "zoom mains", "vue éclatée", "focus boulons"],
        "data_testids": [
          "regen-panel-toggle",
          "regen-panel-textarea",
          "regen-suggestion-chip",
          "regen-submit-button"
        ]
      },
      "share": {
        "behavior": "Share button copies public URL and triggers success toast 'Lien copié !'",
        "data_testid": "manual-share-button"
      }
    },

    "credits": {
      "route": "/credits",
      "layout": {
        "pricing": "2-column plan cards (Gratuit | Pro) with 'Recommandé' badge on Pro.",
        "packs": "3 credit pack cards in a 3-col grid; quantities in mono, violet-bright."
      },
      "data_testids": [
        "credits-plan-free",
        "credits-plan-pro",
        "credits-pack-5",
        "credits-pack-15",
        "credits-pack-40"
      ]
    },

    "settings": {
      "route": "/settings",
      "layout": "4 section cards: Profil, Modèle IA, Préférences, Zone de danger",
      "rows": "Each row: label left (text2) + value right (text) or Switch; use separators.",
      "danger": "Danger buttons use btn--d.",
      "data_testids": [
        "settings-profile-section",
        "settings-model-section",
        "settings-preferences-section",
        "settings-danger-section"
      ]
    },

    "share_public": {
      "route": "/share/:id",
      "chrome": "Standalone viewer only",
      "differences": [
        "No sidebar",
        "No topbar editing actions",
        "No regenerate buttons/panels",
        "Read-only"
      ],
      "layout": "Use the same viewer right-side content but within shareWrap max-width container.",
      "data_testids": [
        "share-viewer",
        "share-step-title",
        "share-step-image"
      ]
    }
  },

  "motion_and_microinteractions": {
    "principles": [
      "Subtle, premium: 120–180ms for hover, 220–320ms for panels/step transitions.",
      "No bouncy easing; use ease-out / cubic-bezier(0.2, 0.8, 0.2, 1).",
      "Respect prefers-reduced-motion: disable spinner/entrance animations."
    ],
    "card_hover": "transition: box-shadow 160ms ease, border-color 160ms ease, background-color 160ms ease; transform on hover translateY(-1px) with transition: transform 160ms ease (explicit).",
    "step_transitions": "Use framer-motion AnimatePresence for wizard step content: fade + slight y (6px).",
    "toast": "Sonner toasts slide-in from bottom-right with opacity + translateY; no scale.",
    "progress_fill": "Width transition 400ms ease (already in .pr > span)."
  },

  "loading_skeletons_and_empty_states": {
    "skeletons": {
      "manual_card": "Skeleton title line + 2 meta lines + action row; keep within gc card.",
      "viewer_image": "Large Skeleton block with subtle shimmer; avoid bright shimmer; use rgba(30,27,42,.55).",
      "chat": "3 skeleton bubbles alternating left/right."
    },
    "empty_states": {
      "no_manuals": {
        "copy": "Aucun manuel pour l’instant. Créez votre premier manuel en 2 minutes.",
        "cta": "Primary '✦ Nouveau'",
        "visual": "Small line icon + dashed border card (still dark)."
      },
      "no_credits": {
        "copy": "Vous n’avez plus de crédits. Choisissez un pack pour continuer.",
        "cta": "Scroll to packs; highlight with gc--hi border."
      }
    }
  },

  "component_path": {
    "shadcn_allowed_for_forms_and_utilities": [
      "/app/frontend/src/components/ui/input.jsx",
      "/app/frontend/src/components/ui/label.jsx",
      "/app/frontend/src/components/ui/textarea.jsx",
      "/app/frontend/src/components/ui/button.jsx",
      "/app/frontend/src/components/ui/switch.jsx",
      "/app/frontend/src/components/ui/sheet.jsx",
      "/app/frontend/src/components/ui/scroll-area.jsx",
      "/app/frontend/src/components/ui/skeleton.jsx",
      "/app/frontend/src/components/ui/progress.jsx",
      "/app/frontend/src/components/ui/sonner.jsx"
    ],
    "note": "Prefer custom App.css classes for chrome (sidebar/topbar/cards/buttons) to match reference exactly; use shadcn primitives only where it doesn't fight the design."
  },

  "image_urls": {
    "note": "Reference design appears icon/shape-driven; no external photography required. Use generated manual images from gpt-image-1. For placeholders, use CSS skeletons instead of stock images.",
    "categories": [
      {
        "category": "manual_step_image_placeholder",
        "description": "Use Skeleton blocks; do not use stock photos.",
        "urls": []
      }
    ]
  },

  "instructions_to_main_agent": [
    "Create/replace /app/frontend/src/App.css with the tokens + classes above; remove CRA demo styles.",
    "Do NOT rely on shadcn theme tokens in index.css; keep shadcn components but override via className to match ManuelIA variables.",
    "Implement app shell with fixed sidebar (232px) + topbar (58px) + scrollable content.",
    "Add noise overlay + two blurred violet blobs globally.",
    "Ensure /share/:id uses standalone layout (no sidebar/topbar, no regen actions).",
    "Add data-testid to every interactive element and key info text (stats numbers, status text, progress label, etc.).",
    "No purple/pink gradients rule is overridden by explicit user choice: violet accents are mandatory; keep gradients minimal and only for small avatar/halo accents (<=20% viewport)."
  ],

  "appendix_general_ui_ux_design_guidelines": "<General UI UX Design Guidelines>\n    - You must **not** apply universal transition. Eg: `transition: all`. This results in breaking transforms. Always add transitions for specific interactive elements like button, input excluding transforms\n    - You must **not** center align the app container, ie do not add `.App { text-align: center; }` in the css file. This disrupts the human natural reading flow of text\n   - NEVER: use AI assistant Emoji characters like`🤖🧠💭💡🔮🎯📚🎭🎬🎪🎉🎊🎁🎀🎂🍰🎈🎨🎰💰💵💳🏦💎🪙💸🤑📊📈📉💹🔢🏆🥇 etc for icons. Always use **FontAwesome cdn** or **lucid-react** library already installed in the package.json\n\n **GRADIENT RESTRICTION RULE**\nNEVER use dark/saturated gradient combos (e.g., purple/pink) on any UI element.  Prohibited gradients: blue-500 to purple 600, purple 500 to pink-500, green-500 to blue-500, red to pink etc\nNEVER use dark gradients for logo, testimonial, footer etc\nNEVER let gradients cover more than 20% of the viewport.\nNEVER apply gradients to text-heavy content or reading areas.\nNEVER use gradients on small UI elements (<100px width).\nNEVER stack multiple gradient layers in the same viewport.\n\n**ENFORCEMENT RULE:**\n    • Id gradient area exceeds 20% of viewport OR affects readability, **THEN** use solid colors\n\n**How and where to use:**\n   • Section backgrounds (not content backgrounds)\n   • Hero section header content. Eg: dark to light to dark color\n   • Decorative overlays and accent elements only\n   • Hero section with 2-3 mild color\n   • Gradients creation can be done for any angle say horizontal, vertical or diagonal\n\n- For AI chat, voice application, **do not use purple color. Use color like light green, ocean blue, peach orange etc**\n\n</Font Guidelines>\n\n- Every interaction needs micro-animations - hover states, transitions, parallax effects, and entrance animations. Static = dead. \n   \n- Use 2-3x more spacing than feels comfortable. Cramped designs look cheap.\n\n- Subtle grain textures, noise overlays, custom cursors, selection states, and loading animations: separates good from extraordinary.\n   \n- Before generating UI, infer the visual style from the problem statement (palette, contrast, mood, motion) and immediately instantiate it by setting global design tokens (primary, secondary/accent, background, foreground, ring, state colors), rather than relying on any library defaults. Don't make the background dark as a default step, always understand problem first and define colors accordingly\n    Eg: - if it implies playful/energetic, choose a colorful scheme\n           - if it implies monochrome/minimal, choose a black–white/neutral scheme\n\n**Component Reuse:**\n\t- Prioritize using pre-existing components from src/components/ui when applicable\n\t- Create new components that match the style and conventions of existing components when needed\n\t- Examine existing components to understand the project's component patterns before creating new ones\n\n**IMPORTANT**: Do not use HTML based component like dropdown, calendar, toast etc. You **MUST** always use `/app/frontend/src/components/ui/ ` only as a primary components as these are modern and stylish component\n\n**Best Practices:**\n\t- Use Shadcn/UI as the primary component library for consistency and accessibility\n\t- Import path: ./components/[component-name]\n\n**Export Conventions:**\n\t- Components MUST use named exports (export const ComponentName = ...)\n\t- Pages MUST use default exports (export default function PageName() {...})\n\n**Toasts:**\n  - Use `sonner` for toasts\"\n  - Sonner component are located in `/app/src/components/ui/sonner.tsx`\n\nUse 2–4 color gradients, subtle textures/noise overlays, or CSS-based noise to avoid flat visuals.\n</General UI UX Design Guidelines>"
}
