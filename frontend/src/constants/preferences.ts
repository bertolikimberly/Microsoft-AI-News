// IDs must match the slugs produced by seed.py's tag_slug() from sources.json tags_taxonomy.
export const PREF_ROLES = [
  { id: 'for_engineers_technical_depth', label: 'For engineers',          note: 'Technical depth — model details, code, infra',     defaultDepth: 'deep'  },
  { id: 'for_business_sales',            label: 'For business & sales',   note: 'Markets, deals, what to tell customers',           defaultDepth: 'short' },
  { id: 'for_legal_compliance',          label: 'For legal & compliance', note: 'Regulation, antitrust, privacy law',               defaultDepth: 'short' },
  { id: 'for_executives_strategic',      label: 'For executives',         note: 'Strategic, high-level signals',                    defaultDepth: 'short' },
  { id: 'for_researchers',               label: 'For researchers',        note: 'Papers, benchmarks, deep technical reads',         defaultDepth: 'deep'  },
]

export const TOPIC_GROUPS = [
  {
    id: 'topic', label: 'Technology', note: 'Core tech beats',
    items: [
      { id: 'artificial_intelligence_ml',   label: 'AI & ML' },
      { id: 'ai_tools_productivity',        label: 'AI Tools & Productivity' },
      { id: 'creative_ai_generative_media', label: 'Creative AI & Generative Media' },
      { id: 'cybersecurity',                label: 'Cybersecurity' },
      { id: 'cloud_infrastructure',         label: 'Cloud & Infrastructure' },
      { id: 'software_development',         label: 'Software Development' },
      { id: 'hardware_chips',               label: 'Hardware & Chips' },
      { id: 'data_privacy',                 label: 'Data & Privacy' },
      { id: 'quantum_computing',            label: 'Quantum Computing' },
      { id: 'robotics_automation',          label: 'Robotics & Automation' },
      { id: 'fintech_payments',             label: 'Fintech & Payments' },
      { id: 'health_biotech',               label: 'Health & Biotech' },
      { id: 'clean_tech_sustainability',    label: 'Clean Tech & Sustainability' },
      { id: 'space_satellites',             label: 'Space & Satellites' },
      { id: 'metaverse_xr',                 label: 'Metaverse & XR' },
    ],
  },
  {
    id: 'business', label: 'Business', note: 'Money, deals, who\'s hiring',
    items: [
      { id: 'ma_funding',               label: 'M&A & Funding' },
      { id: 'ipo_markets',              label: 'IPO & Markets' },
      { id: 'big_tech_faang_microsoft', label: 'Big Tech (FAANG+Microsoft)' },
      { id: 'startups_venture',         label: 'Startups & Venture' },
      { id: 'layoffs_hiring',           label: 'Layoffs & Hiring' },
      { id: 'earnings_revenue',         label: 'Earnings & Revenue' },
    ],
  },
  {
    id: 'regulation', label: 'Regulation & Policy', note: 'Rules of the game',
    items: [
      { id: 'ai_regulation',                  label: 'AI Regulation' },
      { id: 'data_protection_gdpr_dpdp_lgpd', label: 'Data Protection (GDPR, DPDP, LGPD)' },
      { id: 'antitrust_competition',           label: 'Antitrust & Competition' },
      { id: 'export_controls_sanctions',       label: 'Export Controls & Sanctions' },
      { id: 'digital_infrastructure_policy',   label: 'Digital Infrastructure Policy' },
      { id: 'cybersecurity_policy',            label: 'Cybersecurity Policy' },
      { id: 'platform_regulation',             label: 'Platform Regulation' },
    ],
  },
]

// IDs match backend Length literal: 'short' | 'standard' | 'deep'
export const PREF_DEPTHS = [
  { id: 'deep',  label: 'Deep dive', note: 'IC level — long-form, technical, with full context' },
  { id: 'short', label: 'Brief',     note: 'Exec level — short, decision-focused, no jargon' },
]

export const PREF_DELIVERY = [
  { id: 'daily',    label: 'Daily brief',          note: 'Every morning, ranked and deduplicated' },
  { id: 'weekly',   label: 'Weekly digest',        note: 'One Sunday long-read of what mattered' },
  { id: 'breaking', label: 'Breaking-news alerts', note: 'Only when your keywords show up' },
]

// IDs match backend Tone literal: 'executive' | 'business' | 'technical'
export const PREF_TONES = [
  { id: 'executive', label: 'Calm & editorial' },
  { id: 'business',  label: 'Plain & direct' },
  { id: 'technical', label: 'Technical' },
]
