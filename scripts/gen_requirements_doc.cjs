const fs = require('fs');
const docx = require('/Users/maoshanbo/.workbuddy/binaries/node/workspace/node_modules/docx');

// Use docx. prefix for all types
const P = docx.Paragraph;
const T = docx.TextRun;
const Tbl = docx.Table;
const TR = docx.TableRow;
const TC = docx.TableCell;
const Hdr = docx.Header;
const Ftr = docx.Footer;
const AT = docx.AlignmentType;
const HL = docx.HeadingLevel;
const BS = docx.BorderStyle;
const WT = docx.WidthType;
const ST = docx.ShadingType;
const PN = docx.PageNumber;
const PB = docx.PageBreak;
const LF = docx.LevelFormat;

const border = { style: BS.SINGLE, size: 1, color: "CCCCCC" };
const borders = { top: border, bottom: border, left: border, right: border };
const cellMargins = { top: 60, bottom: 60, left: 100, right: 100 };
const headerBg = { fill: "1A365D", type: ST.CLEAR };

function h1(text) {
  return new P({ heading: HL.HEADING_1, children: [new T({ text, bold: true, size: 32, font: "Arial" })] });
}
function h2(text) {
  return new P({ heading: HL.HEADING_2, children: [new T({ text, bold: true, size: 28, font: "Arial" })] });
}
function h3(text) {
  return new P({ heading: HL.HEADING_3, children: [new T({ text, bold: true, size: 24, font: "Arial" })] });
}
function p(text) {
  return new P({ children: [new T({ text, size: 22, font: "Arial" })] });
}
function boldP(label, value) {
  return new P({ children: [
    new T({ text: label, bold: true, size: 22, font: "Arial" }),
    new T({ text: value, size: 22, font: "Arial" })
  ] });
}
function sp() {
  return new P({ children: [new T({ text: "", size: 12 })] });
}
function hdrCell(text, width) {
  return new TC({
    borders, width: { size: width, type: WT.DXA }, shading: headerBg, margins: cellMargins,
    children: [new P({ children: [new T({ text, bold: true, size: 20, font: "Arial", color: "FFFFFF" })] })]
  });
}
function cell(text, width) {
  return new TC({
    borders, width: { size: width, type: WT.DXA }, margins: cellMargins,
    children: [new P({ children: [new T({ text, size: 20, font: "Arial" })] })]
  });
}
function row(cells) { return new TR({ children: cells }); }

const cw = 9026;

// ===================== DOCUMENT CONTENT =====================

const children = [
  // ===== TITLE PAGE =====
  new P({ alignment: AT.CENTER, spacing: { before: 3000 }, children: [
    new T({ text: "allfund.cn \u6295\u8D44\u5DE5\u4F5C\u52A9\u624B", bold: true, size: 44, font: "Arial" })
  ] }),
  new P({ alignment: AT.CENTER, spacing: { before: 200 }, children: [
    new T({ text: "\u9700\u6C42\u6587\u6863\u4E0E\u8FED\u4EE3\u8BB0\u5F55", bold: true, size: 36, font: "Arial" })
  ] }),
  new P({ alignment: AT.CENTER, spacing: { before: 600 }, children: [
    new T({ text: "\u7248\u672C\uFF1AV1.0  |  \u65E5\u671F\uFF1A2026-06-10", size: 24, font: "Arial", color: "666666" })
  ] }),
  new P({ alignment: AT.CENTER, spacing: { before: 100 }, children: [
    new T({ text: "\u9879\u76EE\u5730\u5740\uFF1Ahttps://www.allfund.cn", size: 24, font: "Arial", color: "666666" })
  ] }),

  new P({ children: [new PB()] }),

  // ===== TOC =====
  h1("\u76EE\u5F55"),
  sp(),
  p("\u4E00\u3001\u6587\u6863\u6982\u8FF0"),
  p("\u4E8C\u3001\u9700\u6C42\u603B\u89C8"),
  p("\u4E09\u3001\u9700\u6C42\u8BE6\u60C5\uFF08R-001 ~ R-009\uFF09"),
  p("\u56DB\u3001Bug \u4FEE\u590D\u8BB0\u5F55\uFF08B-001 ~ B-004\uFF09"),
  p("\u4E94\u3001\u90E8\u7F72\u8BB0\u5F55"),
  p("\u516D\u3001\u9644\u5F55\uFF1A\u5B8C\u6574\u6587\u4EF6\u53D8\u66F4\u6E05\u5355"),

  new P({ children: [new PB()] }),

  // ===== 一、文档概述 =====
  h1("\u4E00\u3001\u6587\u6863\u6982\u8FF0"),
  sp(),
  boldP("\u9879\u76EE\u540D\u79F0\uFF1A", "allfund.cn \u6295\u8D44\u5DE5\u4F5C\u52A9\u624B H5"),
  boldP("\u6280\u672F\u6808\uFF1A", "Vue 3 + Vite + Vue Router 4 + Supabase + ECharts"),
  boldP("\u90E8\u7F72\u5E73\u53F0\uFF1A", "\u817E\u8BAF\u4E91 EdgeOne Pages"),
  boldP("\u6570\u636E\u5E93\uFF1A", "Supabase\uFF08\u65B0\u52A0\u5761\u8282\u70B9\uFF09"),
  boldP("\u6587\u6863\u76EE\u7684\uFF1A", "\u8BB0\u5F55 2026-06-09 \u81F3 2026-06-10 \u671F\u95F4\u6240\u6709\u529F\u80FD\u9700\u6C42\u3001\u5B9E\u73B0\u65B9\u6848\u3001\u8FED\u4EE3\u4FEE\u6539\u53CA Bug \u4FEE\u590D\u3002"),
  sp(),
  p("\u672C\u6587\u6863\u6309\u7167\u9700\u6C42\u63D0\u51FA\u7684\u65F6\u95F4\u987A\u5E8F\u6392\u5217\uFF0C\u5171\u6DB5\u76D6 9 \u4E2A\u529F\u80FD\u9700\u6C42\u548C 4 \u4E2A Bug \u4FEE\u590D\u3002"),

  new P({ children: [new PB()] }),

  // ===== 二、需求总览 =====
  h1("\u4E8C\u3001\u9700\u6C42\u603B\u89C8"),
  sp(),
  new Tbl({
    width: { size: cw, type: WT.DXA },
    columnWidths: [1600, 2800, 1200, 3426],
    rows: [
      row([hdrCell("\u9700\u6C42\u7F16\u53F7", 1600), hdrCell("\u9700\u6C42\u540D\u79F0", 2800), hdrCell("\u72B6\u6001", 1200), hdrCell("\u5173\u8054 Bug", 3426)]),
      row([cell("R-001", 1600), cell("L2 \u4E8C\u7EA7\u5206\u7C7B\u7B5B\u9009\u4FEE\u590D", 2800), cell("\u5DF2\u5B8C\u6210", 1200), cell("\u65E0", 3426)]),
      row([cell("R-002", 1600), cell("\u5B8F\u89C2\u6307\u6807\u65F6\u95F4\u8303\u56F4\u4F18\u5316", 2800), cell("\u5DF2\u5B8C\u6210", 1200), cell("\u65E0", 3426)]),
      row([cell("R-003", 1600), cell("\u70B9\u8D5E/\u5410\u69FD\u529F\u80FD", 2800), cell("\u5DF2\u5B8C\u6210", 1200), cell("\u65E0", 3426)]),
      row([cell("R-004", 1600), cell("\u7528\u6237\u8BA4\u8BC1\u7CFB\u7EDF", 2800), cell("\u5DF2\u5B8C\u6210", 1200), cell("B-001 \u5F71\u54CD", 3426)]),
      row([cell("R-005", 1600), cell("\u57FA\u91D1\u5217\u8868 \"+\" \u6309\u94AE", 2800), cell("\u5DF2\u5B8C\u6210", 1200), cell("B-001 \u5F71\u54CD", 3426)]),
      row([cell("R-006", 1600), cell("\u6295\u8D44\u7EC4\u5408\u56DE\u6D4B\u529F\u80FD", 2800), cell("\u5DF2\u5B8C\u6210", 1200), cell("B-001 \u5F71\u54CD", 3426)]),
      row([cell("R-007", 1600), cell("\u6253\u5206\u989C\u8272\u6E10\u53D8\u4F18\u5316", 2800), cell("\u5DF2\u5B8C\u6210", 1200), cell("B-001 \u4E3B\u8981\u89E6\u53D1", 3426)]),
      row([cell("R-008", 1600), cell("\u7EC4\u5408\u51C0\u503C\u8D70\u52BF\u56FE", 2800), cell("\u5DF2\u5B8C\u6210\uFF0C\u5F85\u91CD\u65B0\u9A8C\u8BC1", 1200), cell("B-001 \u5F71\u54CD", 3426)]),
      row([cell("R-009", 1600), cell("\u6307\u6570\u4F30\u503C\u6A21\u5757\u8FC1\u79FB", 2800), cell("\u5DF2\u5B8C\u6210\uFF0C\u5F85\u91CD\u65B0\u9A8C\u8BC1", 1200), cell("B-001 \u5F71\u54CD", 3426)]),
    ]
  }),
  sp(),
  p("\u8BF4\u660E\uFF1AB-001\uFF08scoreBg is not defined\uFF09Bug \u5F71\u54CD\u8303\u56F4\u6DB5\u76D6 R-004 ~ R-009 \u6240\u6709\u529F\u80FD\u3002\u4EE3\u7801\u56DE\u9000\u540E\u8FD9\u4E9B\u529F\u80FD\u9700\u91CD\u65B0\u9A8C\u8BC1\u6216\u6062\u590D\u3002"),

  new P({ children: [new PB()] }),

  // ===== 三、需求详情 =====
  h1("\u4E09\u3001\u9700\u6C42\u8BE6\u60C5"),

  // --- R-001 ---
  h2("3.1 R-001\uFF1AL2 \u4E8C\u7EA7\u5206\u7C7B\u7B5B\u9009\u4FEE\u590D"),
  sp(),
  h3("\u80CC\u666F"),
  p("\u5728 FundRankPage\uFF08\u9760\u8C31\u57FA\u91D1\u6307\u6570\u9875\uFF09\u4F7F\u7528\u4E8C\u7EA7\u5206\u7C7B\u7B5B\u9009\u65F6\uFF0C\u6240\u6709\u5B50\u7C7B\u4EA7\u54C1\u6570\u91CF\u5747\u663E\u793A\u4E3A 0\uFF0C\u7B5B\u9009\u529F\u80FD\u5931\u6548\u3002"),
  h3("\u6839\u56E0"),
  p("computeClassStats() \u5728\u8FD0\u884C\u65F6\u4ECE 2.8MB \u5206\u7C7B\u6570\u636E\u6587\u4EF6\u52A8\u6001\u8BA1\u7B97\u7EDF\u8BA1\u4FE1\u606F\u3002Vite \u6A21\u5757\u52A0\u8F7D\u65F6\u5E8F\u95EE\u9898\u5BFC\u81F4\u6570\u636E\u5728\u7EC4\u4EF6\u6E32\u67D3\u65F6\u672A\u5C31\u7EEA\uFF0C\u7EDF\u8BA1\u7ED3\u679C\u59CB\u7EC8\u4E3A\u7A7A\u3002"),
  h3("\u89E3\u51B3\u65B9\u6848"),
  p("1. \u6539\u4E3A\u9884\u8BA1\u7B97\u9759\u6001\u6587\u4EF6 class-stats.js\uFF086KB\uFF09\uFF0C\u5728\u6784\u5EFA\u65F6\u63D0\u524D\u8BA1\u7B97\u5206\u7C7B\u7EDF\u8BA1"),
  p("2. FundRankPage.vue \u76F4\u63A5\u4ECE\u9759\u6001\u6587\u4EF6\u5BFC\u5165\uFF0C\u65E0\u9700\u8FD0\u884C\u65F6\u8BA1\u7B97"),
  p("3. \u540C\u65F6\u5B58\u50A8\u5230 Supabase config \u8868\u4F5C\u4E3A\u5907\u4EFD"),
  h3("\u6D89\u53CA\u6587\u4EF6"),
  p("  - allfund/src/data/class-stats.js\uFF08\u65B0\u589E\uFF09"),
  p("  - allfund/src/pages/fund-rank/FundRankPage.vue\uFF08\u4FEE\u6539\uFF09"),
  p("  - Supabase config \u8868\uFF08\u65B0\u589E\u6761\u76EE\uFF09"),
  h3("\u8FED\u4EE3\u5386\u53F2"),
  p("  \u65E0\u8FED\u4EE3\uFF0C\u4E00\u6B21\u5B8C\u6210\u3002"),

  new P({ children: [new PB()] }),

  // --- R-002 ---
  h2("3.2 R-002\uFF1A\u5B8F\u89C2\u6307\u6807\u65F6\u95F4\u8303\u56F4\u4F18\u5316"),
  sp(),
  h3("\u80CC\u666F"),
  p("\u5B8F\u89C2\u6307\u6807\u56FE\u8868\u9ED8\u8BA4\u5C55\u793A\u5168\u90E8\u5386\u53F2\u6570\u636E\uFF08\u90E8\u5206\u6307\u6807\u4ECE 2002 \u5E74\u8D77\uFF09\uFF0C\u56FE\u8868\u8FC7\u4E8E\u62E5\u6324\u3002\u7528\u6237\u5E0C\u671B\u9ED8\u8BA4\u5C55\u793A\u6700\u8FD1 10 \u5E74\uFF0C\u5E76\u63D0\u4F9B\u53EF\u62D6\u62FD\u7684\u65F6\u95F4\u8303\u56F4\u9009\u62E9\u5668\u3002"),
  h3("\u89E3\u51B3\u65B9\u6848"),
  p("1. \u4FEE\u590D fetchMacroHistory() \u4E2D\u91CD\u590D\u5FAA\u73AF bug"),
  p("2. ECharts \u6DFB\u52A0 dataZoom \u7EC4\u4EF6\uFF1A"),
  p("   - slider \u7C7B\u578B\uFF1A\u5E95\u90E8\u53EF\u62D6\u62FD\u8303\u56F4\u6761\uFF08\u9ED8\u8BA4\u6700\u8FD1 10 \u5E74\uFF09"),
  p("   - inside \u7C7B\u578B\uFF1A\u9F20\u6807\u6EDA\u8F6E\u7F29\u653E"),
  p("3. \u8C03\u6574 grid.bottom \u4ECE 30 \u2192 50\uFF0C\u4E3A\u6ED1\u5757\u9884\u7559\u7A7A\u95F4"),
  h3("\u6D89\u53CA\u6587\u4EF6"),
  p("  - allfund/src/pages/home/HomePage.vue"),
  h3("\u8FED\u4EE3\u5386\u53F2"),
  p("  \u65E0\u8FED\u4EE3\uFF0C\u4E00\u6B21\u5B8C\u6210\u3002"),

  new P({ children: [new PB()] }),

  // --- R-003 ---
  h2("3.3 R-003\uFF1A\u70B9\u8D5E/\u5410\u69FD\u529F\u80FD"),
  sp(),
  h3("\u80CC\u666F"),
  p("\u7528\u6237\u5E0C\u671B\u6BCF\u5F20\u57FA\u91D1\u5361\u7247\u4E0A\u6DFB\u52A0\u70B9\u8D5E\u548C\u5410\u69FD\u6309\u94AE\uFF0C\u8BB0\u5F55\u5BF9\u57FA\u91D1\u7684\u559C\u597D\u8BC4\u4EF7\u3002"),
  h3("\u89E3\u51B3\u65B9\u6848"),
  p("1. \u6BCF\u5F20\u57FA\u91D1\u5361\u7247\u5E95\u90E8\u6DFB\u52A0 SVG \u70B9\u8D5E/\u5410\u69FD\u56FE\u6807"),
  p("2. localStorage \u5B58\u50A8\u6295\u7968\u6570\u636E\uFF08allfund_votes + allfund_vote_history\uFF09"),
  p("3. \u70B9\u51FB\u5207\u6362\u6295\u7968\u72B6\u6001\uFF08\u70B9\u8D5E/\u53D6\u6D88/\u5410\u69FD\uFF09\uFF0C\u5B9E\u65F6\u66F4\u65B0\u8BA1\u6570"),
  h3("\u6D89\u53CA\u6587\u4EF6"),
  p("  - allfund/src/pages/fund-rank/FundRankPage.vue\uFF08\u4FEE\u6539\uFF09"),
  h3("\u8FED\u4EE3\u5386\u53F2"),
  p("  \u65E0\u8FED\u4EE3\uFF0C\u4E00\u6B21\u5B8C\u6210\u3002"),

  new P({ children: [new PB()] }),

  // --- R-004 ---
  h2("3.4 R-004\uFF1A\u7528\u6237\u8BA4\u8BC1\u7CFB\u7EDF"),
  sp(),
  h3("\u80CC\u666F"),
  p("\u4E3A\u6295\u8D44\u7EC4\u5408\u529F\u80FD\u63D0\u4F9B\u7528\u6237\u8BA4\u8BC1\u652F\u6301\uFF0C\u91C7\u7528\u624B\u673A\u53F7\u6CE8\u518C/\u767B\u5F55\u65B9\u5F0F\uFF0C\u65E0\u9700\u7B2C\u4E09\u65B9\u8D26\u53F7\u3002"),
  h3("\u89E3\u51B3\u65B9\u6848"),
  p("1. \u65B0\u5EFA src/auth/auth.js\uFF1A\u624B\u673A\u53F7\u9A8C\u8BC1\u3001localStorage \u4F1A\u8BDD\u5B58\u50A8\u3001\u6CE8\u518C/\u767B\u5F55/\u767B\u51FA"),
  p("2. \u65B0\u5EFA src/auth/portfolio.js\uFF1A\u7EC4\u5408 CRUD\uFF08\u6BCF\u7528\u6237\u6700\u591A 3 \u4E2A\u7EC4\u5408\uFF09"),
  p("3. \u91CD\u5199 ProfilePage\uFF1A\u767B\u5F55/\u6CE8\u518C\u9762\u677F + \u7EC4\u5408\u5217\u8868\u7BA1\u7406"),
  h3("\u6D89\u53CA\u6587\u4EF6"),
  p("  - allfund/src/auth/auth.js\uFF08\u65B0\u589E\uFF09"),
  p("  - allfund/src/auth/portfolio.js\uFF08\u65B0\u589E\uFF09"),
  p("  - allfund/src/pages/profile/ProfilePage.vue\uFF08\u91CD\u5199\uFF09"),
  h3("\u8FED\u4EE3\u5386\u53F2"),
  p("  \u65E0\u8FED\u4EE3\uFF0C\u4E00\u6B21\u5B8C\u6210\u3002"),

  new P({ children: [new PB()] }),

  // --- R-005 ---
  h2("3.5 R-005\uFF1A\u57FA\u91D1\u5217\u8868 \"+\" \u6309\u94AE"),
  sp(),
  h3("\u80CC\u666F"),
  p("\u7528\u6237\u6D4F\u89C8\u9760\u8C31\u57FA\u91D1\u6307\u6570\u65F6\uFF0C\u5E0C\u671B\u76F4\u63A5\u5C06\u611F\u5174\u8DA3\u7684\u57FA\u91D1\u6DFB\u52A0\u5230\u6295\u8D44\u7EC4\u5408\uFF0C\u65E0\u9700\u624B\u52A8\u8F93\u5165\u4EE3\u7801\u3002"),
  h3("\u89E3\u51B3\u65B9\u6848"),
  p("1. FundRankPage \u6BCF\u5F20\u57FA\u91D1\u5361\u7247\u53F3\u4E0A\u89D2\u6DFB\u52A0 \"+\" \u6309\u94AE"),
  p("2. \u70B9\u51FB\u540E\u6839\u636E\u767B\u5F55\u72B6\u6001\u5F39\u51FA\u4E0D\u540C\u5BF9\u8BDD\u6846\uFF08\u767B\u5F55\u63D0\u793A / \u521B\u5EFA\u7EC4\u5408 / \u9009\u62E9\u7EC4\u5408 + \u8BBE\u6743\u91CD\uFF09"),
  p("3. \u6DFB\u52A0\u540E PortfolioPage \u5B9E\u65F6\u66F4\u65B0"),
  h3("\u6D89\u53CA\u6587\u4EF6"),
  p("  - allfund/src/pages/fund-rank/FundRankPage.vue\uFF08\u4FEE\u6539\uFF09"),
  p("  - allfund/src/auth/portfolio.js\uFF08\u4FEE\u6539\uFF09"),
  h3("\u8FED\u4EE3\u5386\u53F2"),
  p("  \u65E0\u8FED\u4EE3\uFF0C\u4E00\u6B21\u5B8C\u6210\u3002"),

  new P({ children: [new PB()] }),

  // --- R-006 ---
  h2("3.6 R-006\uFF1A\u6295\u8D44\u7EC4\u5408\u56DE\u6D4B\u529F\u80FD"),
  sp(),
  h3("\u80CC\u666F"),
  p("\u7528\u6237\u521B\u5EFA\u6295\u8D44\u7EC4\u5408\u540E\uFF0C\u5E0C\u671B\u67E5\u770B\u7EC4\u5408\u7684\u5386\u53F2\u6536\u76CA\u56DE\u6D4B\uFF0C\u4E86\u89E3\u5404\u5468\u671F\u6536\u76CA\u8868\u73B0\u3002"),
  h3("\u89E3\u51B3\u65B9\u6848"),
  p("1. PortfolioPage \u65B0\u589E\u201C\u6211\u7684\u7EC4\u5408\u201DTab\uFF08\u4ECE\u7CBE\u9009\u7EC4\u5408\u4E2D\u62C6\u5206\uFF09"),
  p("2. \u5F53\u6743\u91CD\u5408\u8BA1 100% \u65F6\uFF0C\u663E\u793A ECharts \u67F1\u72B6\u56DE\u6D4B\u56FE\uFF1A"),
  p("   - \u4ECE Supabase fund_scores_full \u89C6\u56FE\u67E5\u8BE2\u5404\u57FA\u91D1\u5386\u53F2\u6536\u76CA\u7387"),
  p("   - \u6309\u6743\u91CD\u52A0\u6743\u8BA1\u7B97 10 \u4E2A\u5468\u671F\uFF081\u5468~10\u5E74\uFF09\u6536\u76CA"),
  p("   - \u7EA2\u8272\u67F1=\u6B63\u6536\u76CA\uFF0C\u7EFF\u8272\u67F1=\u8D1F\u6536\u76CA\uFF08\u4E2D\u56FD\u80A1\u5E02\u60EF\u4F8B\uFF09"),
  h3("\u6D89\u53CA\u6587\u4EF6"),
  p("  - allfund/src/pages/portfolio/PortfolioPage.vue\uFF08\u91CD\u5199\uFF09"),
  h3("\u8FED\u4EE3\u5386\u53F2"),
  p("  \u65E0\u8FED\u4EE3\uFF0C\u4E00\u6B21\u5B8C\u6210\u3002"),

  new P({ children: [new PB()] }),

  // --- R-007 ---
  h2("3.7 R-007\uFF1A\u6253\u5206\u989C\u8272\u6E10\u53D8\u4F18\u5316"),
  sp(),
  h3("\u80CC\u666F"),
  p("\u539F\u6709\u9760\u8C31\u5206\u989C\u8272\u65B9\u6848\u4E3A\u79BB\u6563\u56DB\u6863\uFF1A\u91D1\u8272(>=80)\u3001\u6A59\u8272(>=60)\u3001\u9752\u8272(>=40)\u3001\u7070\u8272(<40)\u3002\u7528\u6237\u5E0C\u671B\u6539\u4E3A\u7EFF\u2192\u7EA2\u8FDE\u7EED\u6E10\u53D8\u3002"),
  h3("\u89E3\u51B3\u65B9\u6848"),
  p("1. HSL \u8272\u76F8\u6620\u5C04\uFF1Ahue = 120 - score x 1.2"),
  p("   - 0 \u5206 = \u7EFF\uFF08120\u00B0\uFF09 | 50 \u5206 = \u9EC4\u7EFF\uFF0860\u00B0\uFF09 | 100 \u5206 = \u7EA2\uFF080\u00B0\uFF09"),
  p("2. ScoreBadge \u7EC4\u4EF6\u52A8\u6001\u989C\u8272\uFF08\u80CC\u666F\u3001\u8FB9\u6846\u3001\u6587\u5B57\uFF09"),
  p("3. \u79FB\u9664 CSS \u53D8\u91CF\uFF1A--score-gold/orange/cyan/gray"),
  p("4. \u5E2E\u52A9\u5F39\u7A97\u6587\u5B57\u66F4\u65B0\u4E3A\u6E10\u53D8\u8BF4\u660E"),
  h3("\u6D89\u53CA\u6587\u4EF6"),
  p("  - allfund/src/utils/color.js\uFF08\u65B0\u589E scoreColor()\uFF09"),
  p("  - allfund/src/utils/format.js\uFF08\u65B0\u589E scoreBg \u5BFC\u51FA\uFF09"),
  p("  - allfund/src/components/common/ScoreBadge.vue\uFF08\u52A8\u6001\u6837\u5F0F\uFF09"),
  p("  - allfund/src/pages/fund-rank/FundRankPage.vue\uFF08\u79FB\u9664 scoreCls\uFF09"),
  p("  - allfund/src/pages/portfolio/PortfolioPage.vue\uFF08\u79FB\u9664 scoreCls\uFF09"),
  p("  - allfund/src/style.css\uFF08\u79FB\u9664\u79BB\u6563\u5206\u503C\u53D8\u91CF\uFF09"),
  h3("\u8FED\u4EE3\u5386\u53F2"),
  p("  \u4E00\u6B21\u5B8C\u6210\uFF0C\u65E0\u8FED\u4EE3\u3002\u4F46\u8BE5\u9700\u6C42\u662F Bug B-001 \u7684\u4E3B\u8981\u89E6\u53D1\u70B9\uFF08scoreBg \u6A21\u5757\u5BFC\u51FA\u5F02\u5E38\uFF09\u3002"),

  new P({ children: [new PB()] }),

  // --- R-008 ---
  h2("3.8 R-008\uFF1A\u7EC4\u5408\u51C0\u503C\u8D70\u52BF\u56FE"),
  sp(),
  h3("\u80CC\u666F"),
  p("\u7EC4\u5408\u5EFA\u7ACB\u540E\uFF0C\u7528\u6237\u5E0C\u671B\u770B\u5230\u5386\u53F2\u51C0\u503C\u8D70\u52BF\u56FE\uFF0C\u76F4\u89C2\u4E86\u89E3\u7EC4\u5408\u4EF7\u503C\u53D8\u5316\u8D8B\u52BF\uFF0C\u9700\u6BCF\u65E5\u66F4\u65B0\u3002"),
  h3("\u89E3\u51B3\u65B9\u6848"),
  p("1. \u65B0\u5EFA fund-nav.js\uFF1A"),
  p("   - fetchFundNav(code, days)\uFF1A\u4ECE\u5929\u5929\u57FA\u91D1 API \u83B7\u53D6\u5386\u53F2\u51C0\u503C"),
  p("   - \u6570\u636E\u7F13\u5B58\u5230 localStorage\uFF0C\u6BCF\u65E5\u6821\u9A8C\u66F4\u65B0"),
  p("   - fetchMultipleNav(codes, days)\uFF1A\u6279\u91CF\u83B7\u53D6"),
  p("   - calcPortfolioNav(funds, navMap)\uFF1A\u6309\u6743\u91CD\u8BA1\u7B97\u52A0\u6743\u51C0\u503C\u66F2\u7EBF"),
  p("2. PortfolioPage \u65B0\u589E\u201C\u7EC4\u5408\u51C0\u503C\u8D70\u52BF\u201D\u5361\u7247\uFF1A"),
  p("   - ECharts \u6298\u7EBF\u56FE + \u6E10\u53D8\u9762\u79EF\u586B\u5145"),
  p("   - \u5E95\u90E8 dataZoom \u6ED1\u5757"),
  p("   - \u52A0\u8F7D\u72B6\u6001\u63D0\u793A"),
  h3("\u6D89\u53CA\u6587\u4EF6"),
  p("  - allfund/src/utils/fund-nav.js\uFF08\u65B0\u589E\uFF09"),
  p("  - allfund/src/pages/portfolio/PortfolioPage.vue\uFF08\u4FEE\u6539\uFF09"),
  h3("\u8FED\u4EE3\u5386\u53F2"),
  p("  \u7B2C\u4E00\u6B21\u5B9E\u73B0\u5B8C\u6210\u3002\u53D1\u73B0\u4E24\u4E2A\u62FC\u5199 Bug\uFF08localeCompare/json.stringify\uFF09\uFF0C\u5DF2\u4FEE\u590D\u3002\u4EE3\u7801\u56DE\u9000\u540E\u9700\u91CD\u65B0\u6784\u5EFA\u9A8C\u8BC1\u3002"),

  new P({ children: [new PB()] }),

  // --- R-009 ---
  h2("3.9 R-009\uFF1A\u6307\u6570\u4F30\u503C\u6A21\u5757\u8FC1\u79FB"),
  sp(),
  h3("\u80CC\u666F"),
  p("\u539F\u8D44\u4EA7\u914D\u7F6E\u5C0F\u7A0B\u5E8F\u7684\u6307\u6570\u4F30\u503C\u6A21\u5757\u9700\u8FC1\u79FB\u5230 allfund.cn H5 \u9879\u76EE\uFF0C\u5C55\u793A\u5BBD\u57FA\u6307\u6570 PE/PB \u4F30\u503C\u548C\u767E\u5206\u4F4D\u3002"),
  h3("\u89E3\u51B3\u65B9\u6848"),
  p("1. \u6570\u636E\u5C42\u5DF2\u8FC1\u79FB\uFF1Adanjuan-api.js\uFF08fetchDanjuanEva / fetchPEHistory\uFF09"),
  p("   - \u6570\u636E\u6765\u6E90\uFF1A\u86CB\u5377\u57FA\u91D1 API"),
  p("   - \u5386\u53F2\u6570\u636E\u5B58\u50A8\u5230 Supabase index_pe_history \u8868"),
  p("2. IndustryRankPage.vue \u5DF2\u5B8C\u6574\u5B9E\u73B0\uFF1A\u4F30\u503C\u8868\u683C + \u6392\u5E8F + \u7B5B\u9009 + PE\u8D70\u52BF\u56FE"),
  p("3. \u8DEF\u7531\u5DF2\u6CE8\u518C\uFF1A/tools/industry-rank"),
  h3("\u6D89\u53CA\u6587\u4EF6"),
  p("  - allfund/src/api/danjuan-api.js\uFF08\u5DF2\u8FC1\u79FB\uFF09"),
  p("  - allfund/src/pages/industry-rank/IndustryRankPage.vue\uFF08\u5DF2\u8FC1\u79FB\uFF09"),
  p("  - allfund/src/router/index.js\uFF08\u5DF2\u6CE8\u518C\uFF09"),
  h3("\u8FED\u4EE3\u5386\u53F2"),
  p("  \u8BE5\u9875\u9762\u5728\u4EE3\u7801\u56DE\u9000\u524D\u5DF2\u5B8C\u6574\u5B58\u5728\u3002\u5206\u6790\u786E\u8BA4\uFF1A\u8BE5\u6A21\u5757\u5DF2\u8FC1\u79FB\u5B8C\u6210\uFF0C\u65E0\u9700\u989D\u5916\u5F00\u53D1\u3002\u4EE3\u7801\u56DE\u9000\u540E\u9700\u786E\u8BA4\u6587\u4EF6\u5B8C\u6574\u3002"),

  new P({ children: [new PB()] }),

  // ===== 四、Bug 修复记录 =====
  h1("\u56DB\u3001Bug \u4FEE\u590D\u8BB0\u5F55"),

  // --- B-001 ---
  h2("4.1 B-001\uFF1AscoreBg is not defined"),
  sp(),
  h3("\u5F71\u54CD\u8303\u56F4"),
  p("\u6240\u6709\u9875\u9762\u5185\u5BB9\u533A\u57DF\u7A7A\u767D\uFF0C\u4EC5\u4FA7\u8FB9\u680F/\u6807\u9898\u6B63\u5E38\u6E32\u67D3\u3002\u6D89\u53CA R-004 ~ R-009 \u5168\u90E8\u529F\u80FD\u3002"),
  h3("\u5B8C\u6574\u8FED\u4EE3\u65F6\u95F4\u7EBF"),

  new Tbl({
    width: { size: cw, type: WT.DXA },
    columnWidths: [800, 2000, 3100, 3126],
    rows: [
      row([hdrCell("\u8F6E\u6B21", 800), hdrCell("\u90E8\u7F72 ID", 2000), hdrCell("\u4FEE\u590D\u5185\u5BB9", 3100), hdrCell("\u7ED3\u679C", 3126)]),
      row([cell("\u7B2C1\u8F6E", 800), cell("dprgywqrzt7v", 2000),
           cell("App.vue \u6DFB\u52A0\u5168\u5C40\u9519\u8BEF\u6355\u83B7", 3100), cell("\u7528\u6237\u53CD\u9988\u4ECD\u62A5\u76F8\u540C\u9519\u8BEF", 3126)]),
      row([cell("\u7B2C2\u8F6E", 800), cell("dptz7bzuy6gm", 2000),
           cell("App.vue \u4FEE\u590D\u591A\u6839\u8282\u70B9\u6A21\u677F\uFF08app-root \u5305\u88F9\uFF09", 3100), cell("\u7528\u6237\u53CD\u9988\u4ECD\u62A5\u76F8\u540C\u9519\u8BEF", 3126)]),
      row([cell("\u7B2C3\u8F6E", 800), cell("dpb6k9b3xabi", 2000),
           cell("\u6DFB\u52A0 [App] mounted \u8C03\u8BD5\u65E5\u5FD7", 3100), cell("\u7528\u6237\u53CD\u9988\u4ECD\u62A5\u76F8\u540C\u9519\u8BEF", 3126)]),
      row([cell("\u7B2C4\u8F6E", 800), cell("dpr8skhme1vt", 2000),
           cell("color.js import \u8BED\u53E5\u79FB\u81F3\u6587\u4EF6\u9876\u90E8", 3100), cell("\u7528\u6237\u53CD\u9988\u4ECD\u62A5\u76F8\u540C\u9519\u8BEF", 3126)]),
      row([cell("\u7B2C5\u8F6E", 800), cell("dp1n87x20m8p", 2000),
           cell("ScoreBadge.vue \u5185\u8054 scoreBg/scoreColor \u51FD\u6570\uFF1BProgressBar CSS \u4FEE\u590D", 3100), cell("\u7528\u6237\u53CD\u9988\u7F51\u9875\u80FD\u6253\u5F00\u4F46\u65E0\u5185\u5BB9", 3126)]),
      row([cell("\u7B2C6\u8F6E", 800), cell("dpfuajfd5lfc", 2000),
           cell("\u79FB\u9664 keep-alive\uFF1Bmain.js \u6DFB\u52A0 Vue.config.errorHandler", 3100), cell("\u7528\u6237\u53CD\u9988\u9875\u9762\u4ECD\u7A7A\u767D", 3126)]),
      row([cell("\u7B2C7\u8F6E", 800), cell("dphwbe0cd5hz", 2000),
           cell("git checkout -- . + git clean -fd \u56DE\u9000\u5230 commit ca5d195", 3100), cell("\u7528\u6237\u8981\u6C42\u56DE\u9000\u5230 dpxjbhhftnai \u7248\u672C", 3126)]),
      row([cell("\u7B2C8\u8F6E", 800), cell("dpfexs3ja3i0", 2000),
           cell("\u56DE\u9000\u540E\u91CD\u65B0\u6DFB\u52A0 main.js \u5168\u5C40\u9519\u8BEF\u5904\u7406\u5668", 3100), cell("\u7B49\u5F85\u7528\u6237\u9A8C\u8BC1", 3126)]),
    ]
  }),
  sp(),
  h3("\u6839\u56E0\u603B\u7ED3"),
  p("1. color.js \u4E2D import \u8BED\u53E5\u653E\u5728\u6587\u4EF6\u5E95\u90E8\uFF0C\u5BFC\u81F4 ES Module \u89E3\u6790\u5F02\u5E38"),
  p("2. ScoreBadge.vue \u4F9D\u8D56 color.js \u5BFC\u51FA\u7684 scoreBg \u51FD\u6570\uFF0C\u6A21\u5757\u89E3\u6790\u5931\u8D25\u540E\u51FD\u6570\u672A\u5B9A\u4E49"),
  p("3. App.vue \u6A21\u677F\u591A\u6839\u8282\u70B9 + keep-alive \u7EC4\u5408\u52A0\u5267\u6E32\u67D3\u4E0D\u786E\u5B9A\u6027"),
  p("4. \u591A\u8F6E\u4FEE\u590D\u4E2D\u6587\u4EF6\u53D8\u66F4\u9010\u5C42\u53E0\u52A0\uFF0C\u5F62\u6210\u201C\u4FEE\u590D\u7684\u4FEE\u590D\u201D\u8FDE\u9501\u95EE\u9898"),
  p("5. \u6700\u7EC8\u901A\u8FC7\u5B8C\u6574\u4EE3\u7801\u56DE\u9000 + \u57FA\u7EBF\u91CD\u5EFA\u7B56\u7565\u89E3\u51B3"),

  new P({ children: [new PB()] }),

  // --- B-002 ---
  h2("4.2 B-002\uFF1AApp.vue \u6A21\u677F\u591A\u6839\u8282\u70B9"),
  sp(),
  h3("\u73B0\u8C61"),
  p("\u4E3A\u6DFB\u52A0\u5168\u5C40\u9519\u8BEF\u663E\u793A\uFF0CApp.vue \u6A21\u677F\u51FA\u73B0\u4E24\u4E2A\u6839 div\uFF08v-if/v-else \u5206\u5C5E\u4E0D\u540C\u6839\u8282\u70B9\uFF09\uFF0CVue 3 \u5BF9\u6B64\u573A\u666F\u6E32\u67D3\u4E0D\u7A33\u5B9A\u3002"),
  h3("\u4FEE\u590D\u65B9\u6848"),
  p("\u7528\u5355\u4E00 app-root \u5BB9\u5668\u5305\u88F9\u6240\u6709\u5185\u5BB9\uFF0C\u5728\u5BB9\u5668\u5185\u6761\u4EF6\u6E32\u67D3\u9519\u8BEF\u9762\u677F\u548C\u5E94\u7528\u4E3B\u4F53\u3002"),
  h3("\u6D89\u53CA\u6587\u4EF6"),
  p("  - allfund/src/App.vue"),

  // --- B-003 ---
  h2("4.3 B-003\uFF1A\u90E8\u7F72 Token \u73AF\u5883\u53D8\u91CF\u540D"),
  sp(),
  h3("\u73B0\u8C61"),
  p("edgeone pages deploy \u62A5 Token \u9A8C\u8BC1\u5931\u8D25\u3002"),
  h3("\u4FEE\u590D\u65B9\u6848"),
  p(".env.local \u4E2D EDGEONE_PAGES_TOKEN \u2192 EDGEONE_PAGES_API_TOKEN\u3002"),
  h3("\u6D89\u53CA\u6587\u4EF6"),
  p("  - allfund/.env.local"),

  // --- B-004 ---
  h2("4.4 B-004\uFF1Adist.zip \u7F3A\u5931"),
  sp(),
  h3("\u73B0\u8C61"),
  p("npm run build \u540E build \u811A\u672C\u672A\u751F\u6210 dist.zip\uFF0C\u90E8\u7F72\u62A5\u6587\u4EF6\u4E0D\u5B58\u5728\u3002"),
  h3("\u4FEE\u590D\u65B9\u6848"),
  p("\u90E8\u7F72\u524D\u624B\u52A8\u6253\u5305\uFF1Acd dist && zip -r ../dist.zip . -x '*.DS_Store'\u3002\u5EFA\u8BAE\u96C6\u6210\u5230\u811A\u672C\u3002"),

  new P({ children: [new PB()] }),

  // ===== 五、部署记录 =====
  h1("\u4E94\u3001\u90E8\u7F72\u8BB0\u5F55"),
  sp(),
  boldP("\u90E8\u7F72\u5E73\u53F0\uFF1A", "\u817E\u8BAF\u4E91 EdgeOne Pages"),
  boldP("\u9879\u76EE ID\uFF1A", "pages-qdouwrvewjkn"),
  boldP("\u90E8\u7F72\u547D\u4EE4\uFF1A", "npm run build \u2192 zip dist/ \u2192 npx edgeone pages deploy dist.zip -n allfund"),
  boldP("\u57DF\u540D\uFF1A", "https://www.allfund.cn"),
  sp(),

  new Tbl({
    width: { size: cw, type: WT.DXA },
    columnWidths: [800, 1326, 2200, 2300, 2400],
    rows: [
      row([hdrCell("#", 800), hdrCell("\u90E8\u7F72 ID", 1326), hdrCell("\u65F6\u95F4", 2200), hdrCell("\u5185\u5BB9", 2300), hdrCell("\u5907\u6CE8", 2400)]),
      row([cell("1", 800), cell("dpjr75tbm8gp", 1326), cell("06-09 23:05", 2200), cell("R-001 ~ R-006 \u5B8C\u6210", 2300), cell("\u9996\u6279\u529F\u80FD\u5168\u90E8\u4E0A\u7EBF", 2400)]),
      row([cell("2", 800), cell("dpxjbhhftnai", 1326), cell("06-09 23:30", 2200), cell("R-007 \u989C\u8272\u6E10\u53D8", 2300), cell("\u6700\u540E\u7A33\u5B9A\u7248\u672C\uFF08\u76EE\u6807\u56DE\u9000\u70B9\uFF09", 2400)]),
      row([cell("3", 800), cell("dpv9wfm0nogq", 1326), cell("06-10 \u51CC\u6668", 2200), cell("R-008 \u51C0\u503C\u8D70\u52BF\u9996\u7248", 2300), cell("\u5F00\u59CB\u5F15\u5165 Bug", 2400)]),
      row([cell("4~9", 800), cell("\u89C1 B-001 \u8868\u683C", 1326), cell("06-10 \u51CC\u6668", 2200), cell("\u591A\u8F6E Bug \u4FEE\u590D", 2300), cell("scoreBg \u62A5\u9519 6 \u8F6E\u4FEE\u590D", 2400)]),
      row([cell("10", 800), cell("dphwbe0cd5hz", 1326), cell("06-10 \u51CC\u6668", 2200), cell("\u4EE3\u7801\u56DE\u9000\u5230 ca5d195", 2300), cell("Token \u53D8\u91CF\u540D\u4FEE\u590D", 2400)]),
      row([cell("11", 800), cell("dpfexs3ja3i0", 1326), cell("06-10 \u65E9\u4E0A", 2200), cell("\u56DE\u9000\u540E + \u9519\u8BEF\u6355\u83B7", 2300), cell("\u5F53\u524D\u6700\u65B0\u7248\u672C", 2400)]),
    ]
  }),

  new P({ children: [new PB()] }),

  // ===== 六、附录 =====
  h1("\u516D\u3001\u9644\u5F55\uFF1A\u5B8C\u6574\u6587\u4EF6\u53D8\u66F4\u6E05\u5355"),
  sp(),

  h2("\u65B0\u589E\u6587\u4EF6\uFF08\u5171 17 \u4E2A\uFF09"),
  sp(),
  p("  allfund/src/data/class-stats.js                   - \u9884\u8BA1\u7B97\u57FA\u91D1\u5206\u7C7B\u7EDF\u8BA1"),
  p("  allfund/src/auth/auth.js                          - \u7528\u6237\u8BA4\u8BC1\uFF08\u624B\u673A\u53F7\uFF09"),
  p("  allfund/src/auth/portfolio.js                     - \u6295\u8D44\u7EC4\u5408\u7BA1\u7406"),
  p("  allfund/src/utils/color.js                        - \u53CC\u4E3B\u9898 + HSL \u989C\u8272\u7CFB\u7EDF"),
  p("  allfund/src/utils/fund-nav.js                     - \u57FA\u91D1\u51C0\u503C\u83B7\u53D6\u4E0E\u8BA1\u7B97"),
  p("  allfund/src/components/common/ScoreBadge.vue      - \u9760\u8C31\u5206\u5FBD\u7AE0"),
  p("  allfund/src/components/common/HelpModal.vue       - \u901A\u7528\u5E2E\u52A9\u5F39\u7A97"),
  p("  allfund/src/components/common/SectionHeader.vue   - \u533A\u5757\u6807\u9898"),
  p("  allfund/src/components/common/ThemeToggle.vue     - \u4E3B\u9898\u5207\u6362"),
  p("  allfund/src/components/common/RefreshButton.vue   - \u5237\u65B0\u6309\u94AE"),
  p("  allfund/src/components/common/CardBlock.vue       - \u5361\u7247\u5BB9\u5668"),
  p("  allfund/src/components/common/DataPair.vue        - \u6570\u636E\u952E\u503C\u5BF9"),
  p("  allfund/src/components/common/StatCard.vue        - \u7EDF\u8BA1\u5361\u7247"),
  p("  allfund/src/components/common/ChangeLabel.vue     - \u6DA8\u8DCC\u6807\u7B7E"),
  p("  allfund/src/components/common/LoadingSkeleton.vue - \u52A0\u8F7D\u9AA8\u67B6\u5C4F"),
  p("  allfund/src/components/common/EmptyState.vue      - \u7A7A\u72B6\u6001\u63D0\u793A"),
  p("  allfund/src/components/common/ProgressBar.vue     - \u8FDB\u5EA6\u6761"),
  sp(),

  h2("\u4FEE\u6539\u6587\u4EF6\uFF08\u5171 9 \u4E2A\uFF09"),
  sp(),
  p("  allfund/src/pages/fund-rank/FundRankPage.vue      - \u5206\u7C7B\u7B5B\u9009/\u70B9\u8D5E/+\u6309\u94AE/\u989C\u8272"),
  p("  allfund/src/pages/home/HomePage.vue               - \u5B8F\u89C2\u6307\u6807 dataZoom"),
  p("  allfund/src/pages/portfolio/PortfolioPage.vue     - \u91CD\u5199\uFF1A\u56DE\u6D4B+\u51C0\u503C+Tab"),
  p("  allfund/src/pages/profile/ProfilePage.vue         - \u91CD\u5199\uFF1A\u767B\u5F55+\u7EC4\u5408\u7BA1\u7406"),
  p("  allfund/src/App.vue                               - \u6A21\u677F\u4FEE\u590D + \u9519\u8BEF\u6355\u83B7"),
  p("  allfund/src/main.js                               - Vue \u5168\u5C40\u9519\u8BEF\u5904\u7406\u5668"),
  p("  allfund/src/router/index.js                       - \u8DEF\u7531\u6CE8\u518C"),
  p("  allfund/src/style.css                             - \u79FB\u9664\u79BB\u6563\u5206\u503C\u53D8\u91CF"),
  p("  allfund/src/utils/format.js                       - \u65B0\u589E scoreBg \u5BFC\u51FA"),
  p("  allfund/.env.local                                - Token \u53D8\u91CF\u540D\u4FEE\u6B63"),
  sp(),

  p("\u26A0\uFE0F \u4EE3\u7801\u56DE\u9000\u540E\u72B6\u6001\uFF1Agit checkout -- . \u6062\u590D\u4E86 tracked \u6587\u4EF6\uFF0C\u4F46 git clean -fd \u5220\u9664\u4E86\u6240\u6709 untracked \u65B0\u589E\u6587\u4EF6\u3002"),
  p("\u5F53\u524D\u4EE3\u7801\u57FA\u7EBF\u4E3A commit ca5d195\uFF0C\u4E0A\u8FF0\u6240\u6709\u65B0\u589E\u6587\u4EF6\u548C\u4FEE\u6539\u5747\u9700\u6839\u636E\u672C\u9700\u6C42\u6587\u6863\u9010\u4E00\u6062\u590D\u3002"),

  new P({ children: [new PB()] }),

  h1("\u2014 \u6587\u6863\u7ED3\u675F \u2014"),
  sp(),
  p("\u751F\u6210\u65E5\u671F\uFF1A2026-06-10"),
  p("\u751F\u6210\u5DE5\u5177\uFF1AWorkBuddy AI + docx.js"),
  p("\u5EFA\u8BAE\uFF1A\u529F\u80FD\u6062\u590D\u65F6\u4E25\u683C\u6309\u7167\u672C\u6587\u6863\u4E2D\u7684\u201C\u6D89\u53CA\u6587\u4EF6\u201D\u6E05\u5355\u9010\u4E00\u91CD\u5EFA\uFF0C\u6BCF\u5B8C\u6210\u4E00\u4E2A\u9700\u6C42\u5373\u6784\u5EFA\u9A8C\u8BC1\u3002"),
];

// ===================== BUILD =====================
const doc = new docx.Document({
  styles: {
    default: { document: { run: { font: "Arial", size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: "Arial", color: "1A365D" },
        paragraph: { spacing: { before: 360, after: 120 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, font: "Arial", color: "2C5282" },
        paragraph: { spacing: { before: 240, after: 100 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font: "Arial", color: "2B6CB0" },
        paragraph: { spacing: { before: 180, after: 80 }, outlineLevel: 2 } },
    ]
  },
  sections: [{
    properties: {
      page: {
        size: { width: 11906, height: 16838 },
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
      }
    },
    headers: {
      default: new Hdr({ children: [
        new P({ alignment: AT.RIGHT, children: [
          new T({ text: "allfund.cn \u9700\u6C42\u6587\u6863 | V1.0", size: 18, font: "Arial", color: "999999" })
        ] })
      ] })
    },
    footers: {
      default: new Ftr({ children: [
        new P({ alignment: AT.CENTER, children: [
          new T({ text: "\u7B2C ", size: 18, font: "Arial", color: "999999" }),
          new T({ children: [PN.CURRENT], size: 18, font: "Arial", color: "999999" }),
          new T({ text: " \u9875", size: 18, font: "Arial", color: "999999" })
        ] })
      ] })
    },
    children,
  }]
});

const outDir = '/Users/maoshanbo/WorkBuddy/20260405093252/allfund/docs';
const outPath = outDir + '/allfund_requirements.docx';
if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });

docx.Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync(outPath, buffer);
  console.log('Document: ' + outPath);
  console.log('Size: ' + (buffer.length / 1024).toFixed(1) + ' KB');
}).catch(err => {
  console.error('Error:', err);
  process.exit(1);
});
