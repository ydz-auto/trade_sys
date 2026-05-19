const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
        HeadingLevel, BorderStyle, WidthType, ShadingType, AlignmentType } = require('docx');
const fs = require('fs');

const before = JSON.parse(fs.readFileSync('/sessions/6a0ae70048b42c882f2ed38f/workspace/20260506/backend/data_lake/research/all_strategies_backtest_2025_2026.json', 'utf8'));
const after = JSON.parse(fs.readFileSync('/sessions/6a0ae70048b42c882f2ed38f/workspace/20260506/backend/data_lake/research/all_strategies_backtest_2025_2026_optimized.json', 'utf8'));

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

function numCell(num, width, opts = {}) {
    const color = opts.header ? "FFFFFF" : (num > 0 ? "27AE60" : num < 0 ? "E74C3C" : "000000");
    return cell(num > 0 ? "+" + num.toFixed(2) : num.toFixed(2), width, { ...opts, color });
}

// 总体对比表
const overallRows = [
    new TableRow({ cantSplit: true, children: [
        cell("\u6307\u6807", 2000, { header: true }),
        cell("\u4F18\u5316\u524D (10%/10%)", 2000, { header: true, align: AlignmentType.CENTER }),
        cell("\u4F18\u5316\u540E (15%/15%)", 2000, { header: true, align: AlignmentType.CENTER }),
        cell("\u53D8\u5316", 1500, { header: true, align: AlignmentType.CENTER }),
    ]})
];

const bm = before.metrics;
const am = after.metrics;
const comparisons = [
    ["\u603B\u6536\u76CA", bm.return, am.return, "$,", (a,b) => a - b],
    ["\u6536\u76CA\u7387%", bm.return_pct * 100, am.return_pct * 100, "%", (a,b) => (a - b)],
    ["\u6700\u5927\u56DE\u64A4%", bm.max_dd_pct * 100, am.max_dd_pct * 100, "%", (a,b) => (a - b)],
    ["\u590F\u666E\u6BD4\u7387", bm.sharpe, am.sharpe, "", (a,b) => a - b],
    ["\u80DC\u7387%", bm.win_rate * 100, am.win_rate * 100, "%", (a,b) => (a - b)],
    ["\u76C8\u4E8F\u6BD4", bm.profit_factor, am.profit_factor, "", (a,b) => a - b],
    ["\u603B\u4EA4\u6613", bm.total_trades, am.total_trades, "", (a,b) => a - b],
];

comparisons.forEach(([label, b, a, unit, diffFn]) => {
    const delta = diffFn(a, b);
    const deltaStr = delta > 0 ? "+" + delta.toFixed(2) + unit : delta.toFixed(2) + unit;
    const deltaColor = delta > 0 ? "27AE60" : delta < 0 ? "E74C3C" : "7F8C8D";
    overallRows.push(new TableRow({ cantSplit: true, children: [
        cell(label, 2000),
        cell(b.toFixed(2) + unit, 2000, { align: AlignmentType.CENTER }),
        cell(a.toFixed(2) + unit, 2000, { align: AlignmentType.CENTER }),
        cell(deltaStr, 1500, { align: AlignmentType.CENTER, color: deltaColor }),
    ]}));
});

// 平仓原因对比表
const reasonRows = [
    new TableRow({ cantSplit: true, children: [
        cell("\u5E73\u4ED3\u539F\u56E0", 1800, { header: true }),
        cell("\u4F18\u5316\u524D\u6B21\u6570", 1400, { header: true, align: AlignmentType.CENTER }),
        cell("\u4F18\u5316\u524D\u6536\u76CA", 1600, { header: true, align: AlignmentType.RIGHT }),
        cell("\u4F18\u5316\u540E\u6B21\u6570", 1400, { header: true, align: AlignmentType.CENTER }),
        cell("\u4F18\u5316\u540E\u6536\u76CA", 1600, { header: true, align: AlignmentType.RIGHT }),
    ]})
];

const reasons = ["stop_loss", "trailing_stop", "reverse_signal", "end_of_data"];
const reasonNames = { stop_loss: "\u6B62\u635F", trailing_stop: "\u8FFD\u8E2A\u6B62\u76C8", reverse_signal: "\u53CD\u5411\u4FE1\u53F7", end_of_data: "\u6570\u636E\u7ED3\u675F" };

reasons.forEach(r => {
    const b = bm.by_close_reason[r] || { count: 0, total_pnl: 0 };
    const a = am.by_close_reason[r] || { count: 0, total_pnl: 0 };
    reasonRows.push(new TableRow({ cantSplit: true, children: [
        cell(reasonNames[r], 1800),
        cell(b.count.toString(), 1400, { align: AlignmentType.CENTER }),
        cell("$" + b.total_pnl.toLocaleString('en-US', {minimumFractionDigits: 0, maximumFractionDigits: 0}), 1600, { align: AlignmentType.RIGHT, color: b.total_pnl >= 0 ? "27AE60" : "E74C3C" }),
        cell(a.count.toString(), 1400, { align: AlignmentType.CENTER }),
        cell("$" + a.total_pnl.toLocaleString('en-US', {minimumFractionDigits: 0, maximumFractionDigits: 0}), 1600, { align: AlignmentType.RIGHT, color: a.total_pnl >= 0 ? "27AE60" : "E74C3C" }),
    ]}));
});

// 策略对比表
const stratRows = [
    new TableRow({ cantSplit: true, children: [
        cell("\u7B56\u7565", 2000, { header: true }),
        cell("\u4F18\u5316\u524D\u6536\u76CA", 2000, { header: true, align: AlignmentType.RIGHT }),
        cell("\u4F18\u5316\u540E\u6536\u76CA", 2000, { header: true, align: AlignmentType.RIGHT }),
        cell("\u6539\u5584", 1500, { header: true, align: AlignmentType.CENTER }),
    ]})
];

const strategies = ["rsi_14", "macd_12_26_9", "panic_reversal", "leveraged_squeeze", "weak_bounce"];
const stratNames = { rsi_14: "RSI", macd_12_26_9: "MACD", panic_reversal: "Panic Reversal", leveraged_squeeze: "Leveraged Squeeze", weak_bounce: "Weak Bounce" };

strategies.forEach(s => {
    const b = bm.by_strategy[s]?.total_pnl || 0;
    const a = am.by_strategy[s]?.total_pnl || 0;
    const delta = a - b;
    stratRows.push(new TableRow({ cantSplit: true, children: [
        cell(stratNames[s], 2000),
        cell("$" + b.toLocaleString('en-US', {minimumFractionDigits: 0, maximumFractionDigits: 0}), 2000, { align: AlignmentType.RIGHT, color: b >= 0 ? "27AE60" : "E74C3C" }),
        cell("$" + a.toLocaleString('en-US', {minimumFractionDigits: 0, maximumFractionDigits: 0}), 2000, { align: AlignmentType.RIGHT, color: a >= 0 ? "27AE60" : "E74C3C" }),
        cell((delta > 0 ? "+" : "") + "$" + delta.toLocaleString('en-US', {minimumFractionDigits: 0, maximumFractionDigits: 0}), 1500, { align: AlignmentType.CENTER, color: delta >= 0 ? "27AE60" : "E74C3C" }),
    ]}));
});

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
        children: [
            new Paragraph({ heading: HeadingLevel.HEADING_1, alignment: AlignmentType.CENTER, children: [new TextRun("\u4F18\u5316\u524D\u540E\u5BF9\u6BD4\u5206\u6790\u62A5\u544A")] }),
            new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "\u6B62\u635F: 10% \u2192 15% | \u8FFD\u8E2A\u56DE\u6491: 10% \u2192 15%", size: 20, color: "7F8C8D" })] }),
            new Paragraph({ children: [] }),

            new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("\u4E00\u3001\u6838\u5FC3\u6307\u6807\u5BF9\u6BD4")] }),
            new Table({ width: { size: 100, type: WidthType.PERCENTAGE }, columnWidths: [2000, 2000, 2000, 1500], rows: overallRows }),
            new Paragraph({ children: [] }),

            new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("\u4E8C\u3001\u5E73\u4ED3\u539F\u56E0\u5BF9\u6BD4")] }),
            new Table({ width: { size: 100, type: WidthType.PERCENTAGE }, columnWidths: [1800, 1400, 1600, 1400, 1600], rows: reasonRows }),
            new Paragraph({ children: [] }),

            new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("\u4E09\u3001\u7B56\u7565\u6536\u76CA\u5BF9\u6BD4")] }),
            new Table({ width: { size: 100, type: WidthType.PERCENTAGE }, columnWidths: [2000, 2000, 2000, 1500], rows: stratRows }),
            new Paragraph({ children: [] }),

            new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("\u56DB\u3001\u5173\u952E\u53D1\u73B0")] }),
            new Paragraph({ children: [new TextRun({ text: "\u2705 \u79EF\u6781\u53D8\u5316:", bold: true, color: "27AE60" })] }),
            new Paragraph({ children: [new TextRun("1. \u6B62\u635F\u6B21\u6570\u4ECE 4,272 \u51CF\u5C11\u81F3 2,164 (\u51CF\u5C11 49.3%)\uFF0C\u6B62\u635F\u4E8F\u635F\u4ECE -444\u4E07\u51CF\u5C11\u81F3 -332\u4E07 (\u51CF\u5C11 25.2%)")] }),
            new Paragraph({ children: [new TextRun("2. \u6700\u5927\u56DE\u64A4\u4ECE 1019% \u964D\u81F3 854%\uFF0C\u98CE\u9669\u63A7\u5236\u660E\u663E\u6539\u5584")] }),
            new Paragraph({ children: [new TextRun("3. RSI\u7B56\u7565\u4E8F\u635F\u4ECE -4.45\u4E07\u5927\u5E45\u51CF\u5C11\u81F3 -1.05\u4E07 (\u6539\u5584 76%)")] }),
            new Paragraph({ children: [new TextRun("4. Panic Reversal\u76C8\u5229\u4ECE +8,567 \u63D0\u5347\u81F3 +11,235 (\u63D0\u5347 31%)")] }),
            new Paragraph({ children: [] }),

            new Paragraph({ children: [new TextRun({ text: "\u26A0\uFE0F \u9700\u8981\u5173\u6CE8:", bold: true, color: "F39C12" })] }),
            new Paragraph({ children: [new TextRun("1. MACD\u7B56\u7565\u4E8F\u635F\u57FA\u672C\u6301\u5E73 (-31.7\u4E07 vs -32.4\u4E07)\uFF0C\u8BF4\u660E\u8D8B\u52BF\u7B56\u7565\u672C\u8EAB\u9700\u8981\u4F18\u5316")] }),
            new Paragraph({ children: [new TextRun("2. \u8FFD\u8E2A\u6B62\u76C8\u6B21\u6570\u4ECE 7,872 \u51CF\u5C11\u81F3 4,747\uFF0C\u4F46\u603B\u76C8\u5229\u4E5F\u4ECE 385\u4E07\u4E0B\u964D\u81F3 271\u4E07")] }),
            new Paragraph({ children: [new TextRun("3. \u80DC\u7387\u4ECE 47.4% \u4E0B\u964D\u81F3 45.9%\uFF0C\u8BF4\u660E\u653E\u5BBD\u6B62\u635F\u540E\u90E8\u5206\u4EA4\u6613\u6301\u4ED3\u66F4\u4E45\u4F46\u6700\u7EC8\u4ECD\u4E8F\u635F")] }),
            new Paragraph({ children: [] }),

            new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("\u4E94\u3001\u7ED3\u8BBA")] }),
            new Paragraph({ children: [new TextRun({ text: "\u4F18\u5316\u6548\u679C\u8BC4\u4F30: \u6709\u6548\u4F46\u4E0D\u5F7B\u5E95", bold: true, color: "F39C12", size: 24 })] }),
            new Paragraph({ children: [new TextRun("\u2022 \u6B62\u635F\u8FC7\u7D27\u95EE\u9898\u660E\u663E\u6539\u5584\uFF0C\u5047\u6B62\u635F\u5927\u5E45\u51CF\u5C11")] }),
            new Paragraph({ children: [new TextRun("\u2022 \u4F46\u7CFB\u7EDF\u6574\u4F53\u4ECD\u5904\u4E8E\u4E8F\u635F\u72B6\u6001\uFF0C\u6838\u5FC3\u95EE\u9898\u5728\u4E8E\u4FE1\u53F7\u8D28\u91CF")] }),
            new Paragraph({ children: [new TextRun("\u2022 MACD\u7B49\u8D8B\u52BF\u7B56\u7565\u5728\u9707\u8361\u5E02\u4E2D\u9891\u7E41\u4EA7\u751F\u5047\u4FE1\u53F7")] }),
            new Paragraph({ children: [] }),

            new Paragraph({ children: [new TextRun({ text: "\u4E0B\u4E00\u6B65\u5EFA\u8BAE:", bold: true })] }),
            new Paragraph({ children: [new TextRun("1. \u91CD\u70B9\u4F18\u5316\u4FE1\u53F7\u8FC7\u6EE4\u673A\u5236\uFF0C\u51CF\u5C11\u566A\u97F3\u4EA4\u6613")] }),
            new Paragraph({ children: [new TextRun("2. \u8003\u8651\u5E02\u573A\u72B6\u6001\u8BC6\u522B\uFF0C\u8D8B\u52BF\u7B56\u7565\u5728\u9707\u8361\u5E02\u4E2D\u5173\u95ED")] }),
            new Paragraph({ children: [new TextRun("3. \u5C1D\u8BD5\u66F4\u5927\u7684\u6B62\u635F\u5E45\u5EA6 (20%) \u6216 ATR\u52A8\u6001\u6B62\u635F")] }),
        ]
    }]
});

Packer.toBuffer(doc).then(buffer => {
    fs.writeFileSync('/sessions/6a0ae70048b42c882f2ed38f/workspace/优化前后对比分析报告.docx', buffer);
    console.log('对比报告已生成');
});
