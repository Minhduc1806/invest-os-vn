# HF lens data-rich report template

Format chuẩn cho loại báo cáo:

- Pattern: invest-os-vn-bao-cao-hanh-dong-HF-lens-data-rich-YYYY-MM-DD
- Canonical template source: C:\Users\DUC\Desktop\InvestOS_VN_PDF_Reports\invest-os-vn-bao-cao-hanh-dong-HF-lens-data-rich-2026-05-08.pdf
- Local frozen copy: 	emplates\invest-os-vn-bao-cao-hanh-dong-HF-lens-data-rich-template.pdf
- Builder: scripts\build_hf_lens_market_action_template.py

Rule: future reports of this type must use the 2026-05-08 invest-os-vn-bao-cao-hanh-dong-HF-lens-data-rich PDF as canonical layout/style/content-quality template, while refreshing date/data/content for current run.

Content quality rules from anh DUC:
- No placeholder/caveat/metadata text inside report analysis sections.
- If real data exists, analysis must read concrete numbers from data files and produce detailed market interpretation.
- Do not write pipeline descriptions such as “FireAnt bổ sung ngành”, “FireAnt là nguồn chính”, or “Long/short dùng proxy” as market analysis.
- Foreign flow/sector flow must cite real numbers: foreign net by sector, strong/weak money flow sectors, sectors pulling/blocking market, PE/PB only when meaningful.
- Derivatives must cite real numbers: nearest VN30F basis points/%, OI change, foreign net qty/value if available, and interpret basis/OI as risk-on/risk-off proxy.
- If data is missing, state exact missing field, e.g. “thiếu field foreign_net_value”, not generic source/pipeline caveat.
- Section 3 stock signals must never be blank. If no actionable/watch/idea signals exist, explicitly say no buy/watch signal passed and show highest-scored avoid/risk candidates as non-buy monitoring list.
- Native multi-agent lens must not use generic/boilerplate text. Each agent needs concrete numeric evidence in Luận điểm, concrete cross-lens interpretation in Đọc chéo với lens khác, and concrete actionable trigger levels/conditions in Trigger hành động.
- Do not repeat identical “Đọc chéo” or “Trigger” text across agents.
- Before publish, run sanity checks for banned placeholder phrases and ensure PDF exists/size > 0.

Supersedes previous template sources.
