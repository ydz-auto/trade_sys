const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
        HeadingLevel, BorderStyle, WidthType, ShadingType, AlignmentType } = require('docx');
const fs = require('fs');

const data = JSON.parse(fs.readFileSync('/sessions/6a0ae70048b42c882f2ed38f/workspace/20260506/backend/data_lake/research/sltp_analysis_2025_2026.json', 'utf8'));

const border = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const borders = { top: border, bottom: border, left: border, right: border };

function cell(text, width, opts = {}) {
    const { header = false, align = AlignmentType.LEFT, color } = opts;
    return new TableCell({
        borders,
        width: { size: width, type: WidthType.DXA },
        shading: header ? { fill: "2C3E50", type: ShadingType.CLEAR } : undefined,
        margins: { top: 50, bottom: 50, left: 80, right: 80 },
        children: [new Paragraph({
            alignment: align,
            children: [new TextRun({
                text: String(text),
                bold: header || color !== undefined,
                color: color || (header ? "FFFFFF" : "000000"),
                font: { ascii: "Arial", hAnsi: "Arial", eastAsia: "Microsoft YaHei" },
                size: 18
            })]
        })]
    });
}

function pctCell(text, width, opts = {}) {
    const num = parseFloat(text);
    const color = opts.header ? "FFFFFF" : (num >= 50 ? "27AE60" : num >= 40 ? "F39C12" : "E74C3C");
    return cell(text, width, { ...opts, color: opts.header ? "FFFFFF" : color });
}

// 止损时间窗口表
const slTwRows = [
    new TableRow({ cantSplit: true, children: [
        cell("\u65F6\u95F4\u7A97\u53E3", 1600, { header: true }),
        cell("\u5408\u7406\u6B21\u6570", 1200, { header: true, align: AlignmentType.CENTER }),
        cell("\u4E0D\u5408\u7406\u6B21\u6570", 1200, { header: true, align: AlignmentType.CENTER }),
        cell("\u5408\u7406\u7387", 1200, { header: true, align: AlignmentType.CENTER }),
        cell("\u5E73\u5747\u4EF7\u683C\u53D8\u5316", 1600, { header: true, align: AlignmentType.RIGHT }),
        cell("\u4E2D\u4F4D\u6570\u53D8\u5316", 1600, { header: true, align: AlignmentType.RIGHT }),
    ]})
];

const slTw = data.stop_loss.by_time_window;
for (const key of ["6_bars","12_bars","24_bars","48_bars","96_bars","144_bars","288_bars","576_bars"]) {
    const d = slTw[key];
    slTwRows.push(new TableRow({ cantSplit: true, children: [
        cell(`${d.hours}h (${d.minutes}m)`, 1600),
        cell(d.reasonable.toString(), 1200, { align: AlignmentType.CENTER }),
        cell(d.unreasonable.toString(), 1200, { align: AlignmentType.CENTER }),
        pctCell(d.pct_reasonable.toFixed(1) + "%", 1200, { align: AlignmentType.CENTER }),
        cell(d.avg_price_change_pct.toFixed(4) + "%", 1600, { align: AlignmentType.RIGHT }),
        cell(d.median_price_change_pct.toFixed(4) + "%", 1600, { align: AlignmentType.RIGHT }),
    ]}));
}

// 止盈时间窗口表
const tpTwRows = [
    new TableRow({ cantSplit: true, children: [
        cell("\u65F6\u95F4\u7A97\u53E3", 1600, { header: true }),
        cell("\u5408\u7406\u6B21\u6570", 1200, { header: true, align: AlignmentType.CENTER }),
        cell("\u8FC7\u65E9\u6B21\u6570", 1200, { header: true, align: AlignmentType.CENTER }),
        cell("\u5408\u7406\u7387", 1200, { header: true, align: AlignmentType.CENTER }),
        cell("\u5E73\u5747\u4EF7\u683C\u53D8\u5316", 1600, { header: true, align: AlignmentType.RIGHT }),
        cell("\u9519\u8FC7\u7A7A\u95F4", 1600, { header: true, align: AlignmentType.RIGHT }),
    ]})
];

const tpTw = data.take_profit.by_time_window;
for (const key of ["6_bars","12_bars","24_bars","48_bars","96_bars","144_bars","288_bars","576_bars"]) {
    const d = tpTw[key];
    tpTwRows.push(new TableRow({ cantSplit: true, children: [
        cell(`${d.hours}h (${d.minutes}m)`, 1600),
        cell(d.reasonable.toString(), 1200, { align: AlignmentType.CENTER }),
        cell(d.premature.toString(), 1200, { align: AlignmentType.CENTER }),
        pctCell(d.pct_reasonable.toFixed(1) + "%", 1200, { align: AlignmentType.CENTER }),
        cell(d.avg_price_change_pct.toFixed(4) + "%", 1600, { align: AlignmentType.RIGHT }),
        cell(d.avg_extra_move_pct.toFixed(4) + "%", 1600, { align: AlignmentType.RIGHT }),
    ]}));
}

// MAE/MFE 表
const maeRows = [
    new TableRow({ cantSplit: true, children: [
        cell("\u5E73\u4ED3\u539F\u56E0", 1800, { header: true }),
        cell("\u6B21\u6570", 900, { header: true, align: AlignmentType.CENTER }),
        cell("\u5E73\u5747MAE", 1200, { header: true, align: AlignmentType.RIGHT }),
        cell("\u6700\u5927MAE", 1200, { header: true, align: AlignmentType.RIGHT }),
        cell("\u5E73\u5747MFE", 1200, { header: true, align: AlignmentType.RIGHT }),
        cell("\u6700\u5927MFE", 1200, { header: true, align: AlignmentType.RIGHT }),
    ]})
];

const reasonNames = { trailing_stop: "\u8FFD\u8E2A\u6B62\u76C8", reverse_signal: "\u53CD\u5411\u4FE1\u53F7", stop_loss: "\u6B62\u635F", end_of_data: "\u6570\u636E\u7ED3\u675F" };
for (const [key, d] of Object.entries(data.mae_mfe)) {
    if (key === "stop_loss_mae_detail") continue;
    maeRows.push(new TableRow({ cantSplit: true, children: [
        cell(reasonNames[key] || key, 1800),
        cell(d.count.toString(), 900, { align: AlignmentType.CENTER }),
        cell(d.avg_mae_pct.toFixed(4) + "%", 1200, { align: AlignmentType.RIGHT }),
        cell(d.max_mae_pct.toFixed(4) + "%", 1200, { align: AlignmentType.RIGHT }),
        cell(d.avg_mfe_pct.toFixed(4) + "%", 1200, { align: AlignmentType.RIGHT }),
        cell(d.max_mfe_pct.toFixed(4) + "%", 1200, { align: AlignmentType.RIGHT }),
    ]}));
}

const doc = new Document({
    styles: {
        default: {
            document: {
                run: { font: { ascii: "Arial", hAnsi: "Arial", eastAsia: "Microsoft YaHei" }, size: 22 }
            }
        },
        paragraphStyles: [
            { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
              run: { size: 36, bold: true, color: "2C3E50", font: { ascii: "Arial", hAnsi: "Arial", eastAsia: "Microsoft YaHei" } },
              paragraph: { spacing: { before: 240, after: 240 }, outlineLevel: 0, keepNext: false, keepLines: false } },
            { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
              run: { size: 28, bold: true, color: "34495E", font: { ascii: "Arial", hAnsi: "Arial", eastAsia: "Microsoft YaHei" } },
              paragraph: { spacing: { before: 180, after: 180 }, outlineLevel: 1, keepNext: false, keepLines: false } },
        ]
    },
    sections: [{
        properties: {
            page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } }
        },
        children: buildChildren(data)
    }]
});

function buildChildren(data) {
    const maeDetail = data.mae_mfe.stop_loss_mae_detail;
    return [
            new Paragraph({ heading: HeadingLevel.HEADING_1, alignment: AlignmentType.CENTER, children: [new TextRun("\u6B62\u635F\u6B62\u76C8\u5408\u7406\u6027\u5206\u6790\u62A5\u544A")] }),
            new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "\u6570\u636E\u8303\u56F4: 2025-12-01 ~ 2026-04-30 | \u6760\u6746: 50x | \u6B62\u635F: \u672C\u91D110% | \u6B62\u76C8: 60%~1000%", size: 18, color: "7F8C8D" })] }),
            new Paragraph({ children: [] }),

            new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("\u6838\u5FC3\u7ED3\u8BBA")] }),
            new Paragraph({ children: [new TextRun({ text: "\u26A0\uFE0F \u6B62\u635F\u8BBE\u7F6E\u8FC7\u7D27\uFF0C\u662F\u7CFB\u7EDF\u4E8F\u635F\u7684\u4E3B\u8981\u539F\u56E0", bold: true, color: "E74C3C", size: 24 })] }),
            new Paragraph({ children: [] }),

            new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("\u4E00\u3001\u6B62\u635F\u5206\u6790\uFF08" + data.stop_loss.total + " \u7B14\uFF09")] }),
            new Paragraph({ children: [
                new TextRun({ text: "\u5E73\u5747\u4E8F\u635F: ", bold: true }),
                new TextRun({ text: "$" + data.stop_loss.avg_pnl.toLocaleString('en-US', {minimumFractionDigits: 2}), color: "E74C3C", bold: true }),
                new TextRun("  |  \u5E73\u5747\u6301\u4ED3: " + data.stop_loss.avg_hold_hours + " \u5C0F\u65F6  |  \u6B62\u635F\u8DDD\u79BB: " + data.stop_loss.avg_sl_distance_pct + "%")
            ]}),
            new Paragraph({ children: [new TextRun({ text: "\u903B\u8F91\u8BF4\u660E: \u6B62\u635F\u540E\u4EF7\u683C\u7EE7\u7EED\u671D\u4E0D\u5229\u65B9\u5411\u8D70 = \u6B62\u635F\u5408\u7406\uFF1B\u6B62\u635F\u540E\u4EF7\u683C\u53CD\u5F39 = \u6B62\u635F\u8FC7\u7D27", size: 18, color: "7F8C8D" })] }),
            new Paragraph({ children: [] }),
            new Table({ width: { size: 100, type: WidthType.PERCENTAGE }, columnWidths: [1600, 1200, 1200, 1200, 1600, 1600], rows: slTwRows }),
            new Paragraph({ children: [] }),

            new Paragraph({ children: [new TextRun({ text: "\u5173\u952E\u53D1\u73B0:", bold: true, color: "E74C3C" })] }),
            new Paragraph({ children: [new TextRun("1. \u6B62\u635F30\u5206\u949F\u540E\u4EC5 31.1% \u5408\u7406\uFF0C\u610F\u5473\u7740\u8FD1 70% \u7684\u6B62\u635F\u662F\u201C\u5047\u6B62\u635F\u201D\u2014\u2014\u4EF7\u683C\u5728\u6253\u6B62\u635F\u540E\u5FEB\u901F\u53CD\u5F39")] }),
            new Paragraph({ children: [new TextRun("2. \u5373\u4F7F\u7B49\u523024\u5C0F\u65F6\u540E\uFF0C\u5408\u7406\u7387\u4E5F\u53EA\u6709 48.2%\uFF0C\u8BF4\u660E\u6B62\u635F\u65B9\u5411\u5224\u65AD\u672C\u8EAB\u4E5F\u6709\u95EE\u9898")] }),
            new Paragraph({ children: [new TextRun("3. \u5E73\u5747\u6301\u4ED3\u4EC5 0.12 \u5C0F\u65F6\uFF0C\u8BF4\u660E\u5927\u91CF\u6B62\u635F\u5728\u5F00\u4ED3\u540E\u5F88\u77ED\u65F6\u95F4\u5C31\u88AB\u89E6\u53D1")] }),
            new Paragraph({ children: [] }),

            new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("\u4E8C\u3001\u6B62\u76C8\u5206\u6790\uFF08" + data.take_profit.total + " \u7B14\uFF09")] }),
            new Paragraph({ children: [
                new TextRun({ text: "\u5E73\u5747\u76C8\u5229: ", bold: true }),
                new TextRun({ text: "$" + data.take_profit.avg_pnl.toLocaleString('en-US', {minimumFractionDigits: 2}), color: "27AE60", bold: true }),
                new TextRun("  |  \u5E73\u5747\u6301\u4ED3: " + data.take_profit.avg_hold_hours + " \u5C0F\u65F6  |  \u5168\u90E8\u4E3A\u8FFD\u8E2A\u6B62\u76C8")
            ]}),
            new Paragraph({ children: [new TextRun({ text: "\u903B\u8F91\u8BF4\u660E: \u6B62\u76C8\u540E\u4EF7\u683C\u53CD\u8F6C = \u6B62\u76C8\u5408\u7406\uFF1B\u6B62\u76C8\u540E\u4EF7\u683C\u7EE7\u7EED\u8D70 = \u6B62\u76C8\u8FC7\u65E9", size: 18, color: "7F8C8D" })] }),
            new Paragraph({ children: [] }),
            new Table({ width: { size: 100, type: WidthType.PERCENTAGE }, columnWidths: [1600, 1200, 1200, 1200, 1600, 1600], rows: tpTwRows }),
            new Paragraph({ children: [] }),

            new Paragraph({ children: [new TextRun({ text: "\u5173\u952E\u53D1\u73B0:", bold: true, color: "F39C12" })] }),
            new Paragraph({ children: [new TextRun("1. \u6B62\u76C8\u540E30\u5206\u949F\uFF0C58.3% \u7684\u4EA4\u6613\u4EF7\u683C\u7EE7\u7EED\u540C\u65B9\u5411\u8D70\uFF0C\u8BF4\u660E\u8FFD\u8E2A\u6B62\u76C8\u56DE\u6491\u8BBE\u7F6E\u504F\u7D27")] }),
            new Paragraph({ children: [new TextRun("2. \u6B62\u76C8\u540E1\u5C0F\u65F6\u5E73\u5747\u9519\u8FC7 0.0995% \u7684\u4EF7\u683C\u7A7A\u95F4\uFF0C\u5728 50x \u6760\u6746\u4E0B\u76F8\u5F53\u4E8E\u672C\u91D1 4.98% \u7684\u989D\u5916\u6536\u76CA")] }),
            new Paragraph({ children: [new TextRun("3. \u968F\u65F6\u95F4\u63A8\u79FB\uFF0C\u5408\u7406\u7387\u9010\u6E10\u63D0\u5347\u81F3 49.2%\uFF0C\u8BF4\u660E\u77ED\u671F\u56DE\u6491\u5C1A\u53EF\uFF0C\u4F46\u4E2D\u957F\u671F\u504F\u7D27")] }),
            new Paragraph({ children: [] }),

            new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("\u4E09\u3001MAE/MFE \u5206\u6790")] }),
            new Paragraph({ children: [new TextRun({ text: "MAE = \u6301\u4ED3\u671F\u95F4\u6700\u5927\u4E0D\u5229\u504F\u79FB\uFF0CMFE = \u6301\u4ED3\u671F\u95F4\u6700\u5927\u6709\u5229\u504F\u79FB", size: 18, color: "7F8C8D" })] }),
            new Paragraph({ children: [] }),
            new Table({ width: { size: 100, type: WidthType.PERCENTAGE }, columnWidths: [1800, 900, 1200, 1200, 1200, 1200], rows: maeRows }),
            new Paragraph({ children: [] }),

            new Paragraph({ children: [new TextRun({ text: "\u6B62\u635F\u4EA4\u6613 MAE \u8BE6\u60C5:", bold: true })] }),
            new Paragraph({ children: [new TextRun("   \u5E73\u5747 MAE: " + maeDetail.avg_mae + "%  |  \u4E2D\u4F4D\u6570 MAE: " + maeDetail.median_mae + "%  |  \u6B62\u635F\u8DDD\u79BB: " + maeDetail.avg_sl_distance + "%")] }),
            new Paragraph({ children: [new TextRun({ text: "   MAE/\u6B62\u635F\u8DDD\u79BB\u6BD4 = " + maeDetail.mae_to_sl_ratio, bold: true, color: "E74C3C" }),
                new TextRun(" (>1.5 \u8868\u793A\u6B62\u635F\u592A\u7D27\uFF0C\u4EF7\u683C\u7ECF\u5E38\u5148\u6253\u6B62\u635F\u518D\u53CD\u8F6C)")] }),
            new Paragraph({ children: [new TextRun(maeDetail.pct_mae_2x_sl + "% \u7684\u6B62\u635F\u4EA4\u6613\uFF0C\u4EF7\u683C\u56DE\u64A4\u8D85\u8FC7\u6B62\u635F\u8DDD\u79BB\u7684 2 \u500D\uFF0C\u8BF4\u660E\u8FD9\u4E9B\u6B62\u635F\u5B8C\u5168\u53EF\u4EE5\u907F\u514D")] }),
            new Paragraph({ children: [] }),

            new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("\u56DB\u3001\u603B\u7ED3\u4E0E\u5EFA\u8BAE")] }),
            new Paragraph({ children: [] }),

            new Paragraph({ children: [new TextRun({ text: "\u26D4 \u95EE\u9898\u4E00: \u6B62\u635F\u8BBE\u7F6E\u8FC7\u7D27\uFF08\u4E25\u91CD\uFF09", bold: true, color: "E74C3C", size: 24 })] }),
            new Paragraph({ children: [new TextRun("\u73B0\u8C61: 50x \u6760\u6746\u4E0B\uFF0C\u672C\u91D110% \u6B62\u635F\u4EC5\u5141\u8BB8 0.2% \u4EF7\u683C\u6CE2\u52A8")] }),
            new Paragraph({ children: [new TextRun("BTC 5\u5206\u949F\u7EBF\u5E73\u5747\u6CE2\u52A8\u7387\u8FDC\u8D85 0.2%\uFF0C\u5BFC\u81F4\u5927\u91CF\u201C\u5047\u6B62\u635F\u201D")] }),
            new Paragraph({ children: [new TextRun({ text: "\u5EFA\u8BAE: ", bold: true, color: "27AE60" }), new TextRun("\u5C06\u6B62\u635F\u653E\u5BBD\u81F3\u672C\u91D1 15-20%\uFF0C\u6216\u91C7\u7528 ATR \u52A8\u6001\u6B62\u635F")] }),
            new Paragraph({ children: [] }),

            new Paragraph({ children: [new TextRun({ text: "\u26D4 \u95EE\u9898\u4E8C: \u8FFD\u8E2A\u6B62\u76C8\u56DE\u6491\u504F\u7D27\uFF08\u4E2D\u7B49\uFF09", bold: true, color: "F39C12", size: 24 })] }),
            new Paragraph({ children: [new TextRun("\u73B0\u8C61: \u6B62\u76C8\u540E 58% \u7684\u4EA4\u6613\u4EF7\u683C\u7EE7\u7EED\u540C\u65B9\u5411\u8D70\uFF0C\u5E73\u5747\u9519\u8FC7 0.1% \u4EF7\u683C\u7A7A\u95F4")] }),
            new Paragraph({ children: [new TextRun({ text: "\u5EFA\u8BAE: ", bold: true, color: "27AE60" }), new TextRun("\u5C06\u8FFD\u8E2A\u56DE\u6491\u4ECE 10% \u653E\u5BBD\u81F3 15-20%\uFF0C\u6216\u91C7\u7528\u5206\u6B65\u6B62\u76C8")] }),
            new Paragraph({ children: [] }),

            new Paragraph({ children: [new TextRun({ text: "\u26D4 \u95EE\u9898\u4E09: \u4FE1\u53F7\u8FC7\u4E8E\u9891\u7E41\uFF08\u4E2D\u7B49\uFF09", bold: true, color: "F39C12", size: 24 })] }),
            new Paragraph({ children: [new TextRun("\u73B0\u8C61: \u6B62\u635F\u5E73\u5747\u6301\u4ED3\u4EC5 0.12 \u5C0F\u65F6\uFF0C\u6B62\u76C8\u5E73\u5747\u6301\u4ED3\u4EC5 0.15 \u5C0F\u65F6")] }),
            new Paragraph({ children: [new TextRun("\u8BF4\u660E RSI/MACD \u7B49\u7B56\u7565\u4EA7\u751F\u5927\u91CF\u77ED\u671F\u566A\u97F3\u4FE1\u53F7")] }),
            new Paragraph({ children: [new TextRun({ text: "\u5EFA\u8BAE: ", bold: true, color: "27AE60" }), new TextRun("\u589E\u52A0\u4FE1\u53F7\u8FC7\u6EE4\u6761\u4EF6\uFF0C\u5982\u6700\u5C0F\u6CE2\u52A8\u7387\u3001\u6210\u4EA4\u91CF\u7B5B\u9009\u3001\u591A\u7B56\u7565\u786E\u8BA4")] }),
            new Paragraph({ children: [] }),

            new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("\u4E94\u3001\u5EFA\u8BAE\u4F18\u5316\u65B9\u6848")] }),
            new Paragraph({ children: [] }),
            new Paragraph({ children: [new TextRun({ text: "\u65B9\u6848 A: \u4FDD\u5B88\u4F18\u5316", bold: true })] }),
            new Paragraph({ children: [new TextRun("   \u6B62\u635F: \u672C\u91D1 10% \u2192 15%  (0.2% \u2192 0.3% \u4EF7\u683C\u6CE2\u52A8)")] }),
            new Paragraph({ children: [new TextRun("   \u6B62\u76C8\u56DE\u6491: 10% \u2192 15%")] }),
            new Paragraph({ children: [new TextRun("   \u9884\u671F\u6548\u679C: \u51CF\u5C11 30-40% \u7684\u5047\u6B62\u635F")] }),
            new Paragraph({ children: [] }),
            new Paragraph({ children: [new TextRun({ text: "\u65B9\u6848 B: ATR \u52A8\u6001\u6B62\u635F", bold: true })] }),
            new Paragraph({ children: [new TextRun("   \u6B62\u635F = 1.5 \u00D7 ATR(14)")] }),
            new Paragraph({ children: [new TextRun("   \u8FFD\u8E2A\u6B62\u76C8\u56DE\u6491 = 2.0 \u00D7 ATR(14)")] }),
            new Paragraph({ children: [new TextRun("   \u9884\u671F\u6548\u679C: \u81EA\u9002\u5E94\u5E02\u573A\u6CE2\u52A8\u7387")] }),
            new Paragraph({ children: [] }),
            new Paragraph({ children: [new TextRun({ text: "\u65B9\u6848 C: \u964D\u4F4E\u6760\u6746", bold: true })] }),
            new Paragraph({ children: [new TextRun("   \u6760\u6746: 50x \u2192 20x")] }),
            new Paragraph({ children: [new TextRun("   \u6B62\u635F: \u672C\u91D1 10% \u4E0D\u53D8 (0.5% \u4EF7\u683C\u6CE2\u52A8)")] }),
            new Paragraph({ children: [new TextRun("   \u9884\u671F\u6548\u679C: \u663E\u8457\u51CF\u5C11\u5047\u6B62\u635F\uFF0C\u4F46\u5355\u7B14\u76C8\u5229\u4E5F\u4F1A\u964D\u4F4E")] }),
    ];
}

Packer.toBuffer(doc).then(buffer => {
    fs.writeFileSync('/sessions/6a0ae70048b42c882f2ed38f/workspace/\u6B62\u635F\u6B62\u76C8\u5408\u7406\u6027\u5206\u6790\u62A5\u544A.docx', buffer);
    console.log('\u62A5\u544A\u5DF2\u751F\u6210');
});
