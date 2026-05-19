const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
        HeadingLevel, BorderStyle, WidthType, ShadingType, AlignmentType,
        PageBreak } = require('docx');
const fs = require('fs');

// 读取回测结果
const result = JSON.parse(fs.readFileSync('/sessions/6a0ae70048b42c882f2ed38f/workspace/20260506/backend/data_lake/research/all_strategies_backtest_2025_2026.json', 'utf8'));

const border = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const borders = { top: border, bottom: border, left: border, right: border };

// 创建表格单元格
function createCell(text, width, isHeader = false, align = AlignmentType.LEFT) {
    return new TableCell({
        borders,
        width: { size: width, type: WidthType.DXA },
        shading: isHeader ? { fill: "2C3E50", type: ShadingType.CLEAR } : undefined,
        margins: { top: 60, bottom: 60, left: 80, right: 80 },
        children: [new Paragraph({
            alignment: align,
            children: [new TextRun({
                text: text,
                bold: isHeader,
                color: isHeader ? "FFFFFF" : "000000",
                font: { ascii: "Arial", hAnsi: "Arial", eastAsia: "Microsoft YaHei" },
                size: 20
            })]
        })]
    });
}

// 格式化数字
function fmtNum(num) {
    return num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtPct(num) {
    return (num * 100).toFixed(2) + "%";
}

// 策略表格行
const strategyRows = [
    new TableRow({
        cantSplit: true,
        children: [
            createCell("策略名称", 2500, true),
            createCell("交易数", 1200, true, AlignmentType.CENTER),
            createCell("胜率", 1200, true, AlignmentType.CENTER),
            createCell("总收益", 1800, true, AlignmentType.RIGHT),
            createCell("多头", 1000, true, AlignmentType.CENTER),
            createCell("空头", 1000, true, AlignmentType.CENTER),
        ]
    })
];

// 添加策略数据
const strategyData = [
    { name: "RSI Strategy", key: "rsi_14" },
    { name: "MACD Strategy", key: "macd_12_26_9" },
    { name: "Panic Reversal", key: "panic_reversal" },
    { name: "Leveraged Squeeze", key: "leveraged_squeeze" },
    { name: "Weak Bounce", key: "weak_bounce" }
];

strategyData.forEach(s => {
    const data = result.metrics.by_strategy[s.key];
    const pnlColor = data.total_pnl >= 0 ? "27AE60" : "E74C3C";
    strategyRows.push(new TableRow({
        cantSplit: true,
        children: [
            createCell(s.name, 2500),
            createCell(data.count.toString(), 1200, false, AlignmentType.CENTER),
            createCell(fmtPct(data.wins / data.count), 1200, false, AlignmentType.CENTER),
            new TableCell({
                borders,
                width: { size: 1800, type: WidthType.DXA },
                margins: { top: 60, bottom: 60, left: 80, right: 80 },
                children: [new Paragraph({
                    alignment: AlignmentType.RIGHT,
                    children: [new TextRun({
                        text: "$" + fmtNum(data.total_pnl),
                        color: pnlColor,
                        font: { ascii: "Arial", hAnsi: "Arial", eastAsia: "Microsoft YaHei" },
                        size: 20,
                        bold: true
                    })]
                })]
            }),
            createCell(data.longs.toString(), 1000, false, AlignmentType.CENTER),
            createCell(data.shorts.toString(), 1000, false, AlignmentType.CENTER),
        ]
    }));
});

// 平仓原因表格
const exitRows = [
    new TableRow({
        cantSplit: true,
        children: [
            createCell("平仓原因", 3000, true),
            createCell("次数", 1500, true, AlignmentType.CENTER),
            createCell("总收益", 3200, true, AlignmentType.RIGHT),
        ]
    })
];

const exitData = [
    { name: "追踪止盈 (Trailing Stop)", key: "trailing_stop" },
    { name: "反向信号 (Reverse Signal)", key: "reverse_signal" },
    { name: "止损 (Stop Loss)", key: "stop_loss" },
    { name: "数据结束 (End of Data)", key: "end_of_data" }
];

exitData.forEach(e => {
    const data = result.metrics.by_close_reason[e.key];
    if (data) {
        const pnlColor = data.total_pnl >= 0 ? "27AE60" : "E74C3C";
        exitRows.push(new TableRow({
            cantSplit: true,
            children: [
                createCell(e.name, 3000),
                createCell(data.count.toString(), 1500, false, AlignmentType.CENTER),
                new TableCell({
                    borders,
                    width: { size: 3200, type: WidthType.DXA },
                    margins: { top: 60, bottom: 60, left: 80, right: 80 },
                    children: [new Paragraph({
                        alignment: AlignmentType.RIGHT,
                        children: [new TextRun({
                            text: "$" + fmtNum(data.total_pnl),
                            color: pnlColor,
                            font: { ascii: "Arial", hAnsi: "Arial", eastAsia: "Microsoft YaHei" },
                            size: 20,
                            bold: true
                        })]
                    })]
                }),
            ]
        }));
    }
});

const doc = new Document({
    styles: {
        default: {
            document: {
                run: {
                    font: { ascii: "Arial", hAnsi: "Arial", eastAsia: "Microsoft YaHei" },
                    size: 22
                }
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
            page: {
                size: { width: 12240, height: 15840 },
                margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
            }
        },
        children: [
            // 标题
            new Paragraph({
                heading: HeadingLevel.HEADING_1,
                alignment: AlignmentType.CENTER,
                children: [new TextRun("全策略回测报告")]
            }),
            new Paragraph({
                alignment: AlignmentType.CENTER,
                children: [new TextRun({
                    text: `生成时间: ${result.timestamp}`,
                    size: 20,
                    color: "7F8C8D"
                })]
            }),
            new Paragraph({ children: [] }),

            // 回测配置
            new Paragraph({
                heading: HeadingLevel.HEADING_2,
                children: [new TextRun("回测配置")]
            }),
            new Paragraph({
                children: [new TextRun({ text: "数据范围: ", bold: true }), new TextRun(result.data_range)]
            }),
            new Paragraph({
                children: [new TextRun({ text: "初始本金: ", bold: true }), new TextRun("$10,000")]
            }),
            new Paragraph({
                children: [new TextRun({ text: "杠杆倍数: ", bold: true }), new TextRun("50x")]
            }),
            new Paragraph({
                children: [new TextRun({ text: "止损设置: ", bold: true }), new TextRun("本金 10% (价格波动 0.2%)")]
            }),
            new Paragraph({
                children: [new TextRun({ text: "移动止盈: ", bold: true }), new TextRun("初始 60%，最大 1000%，追踪回撤 10%")]
            }),
            new Paragraph({
                children: [new TextRun({ text: "最大持仓: ", bold: true }), new TextRun("48 小时")]
            }),
            new Paragraph({ children: [] }),

            // 总体表现
            new Paragraph({
                heading: HeadingLevel.HEADING_2,
                children: [new TextRun("总体表现")]
            }),
            new Paragraph({
                children: [new TextRun({ text: "总收益: ", bold: true }), new TextRun({
                    text: "$" + fmtNum(result.metrics.return) + " (" + fmtPct(result.metrics.return_pct / 100) + ")",
                    color: result.metrics.return >= 0 ? "27AE60" : "E74C3C",
                    bold: true
                })]
            }),
            new Paragraph({
                children: [new TextRun({ text: "最大回撤: ", bold: true }), new TextRun(fmtPct(result.metrics.max_dd_pct / 100))]
            }),
            new Paragraph({
                children: [new TextRun({ text: "夏普比率: ", bold: true }), new TextRun(result.metrics.sharpe.toFixed(2))]
            }),
            new Paragraph({
                children: [new TextRun({ text: "胜率: ", bold: true }), new TextRun(fmtPct(result.metrics.win_rate))]
            }),
            new Paragraph({
                children: [new TextRun({ text: "盈亏比: ", bold: true }), new TextRun(result.metrics.profit_factor.toFixed(2))]
            }),
            new Paragraph({
                children: [new TextRun({ text: "总交易数: ", bold: true }), new TextRun(result.metrics.total_trades.toString())]
            }),
            new Paragraph({ children: [] }),

            // 策略表现
            new Paragraph({
                heading: HeadingLevel.HEADING_2,
                children: [new TextRun("策略表现")]
            }),
            new Table({
                width: { size: 100, type: WidthType.PERCENTAGE },
                columnWidths: [2500, 1200, 1200, 1800, 1000, 1000],
                rows: strategyRows
            }),
            new Paragraph({ children: [] }),

            // 平仓原因分析
            new Paragraph({
                heading: HeadingLevel.HEADING_2,
                children: [new TextRun("平仓原因分析")]
            }),
            new Table({
                width: { size: 100, type: WidthType.PERCENTAGE },
                columnWidths: [3000, 1500, 3200],
                rows: exitRows
            }),
            new Paragraph({ children: [] }),

            // 关键发现
            new Paragraph({
                heading: HeadingLevel.HEADING_2,
                children: [new TextRun("关键发现")]
            }),
            new Paragraph({
                children: [new TextRun({
                    text: "1. Panic Reversal 策略表现最佳",
                    bold: true
                })]
            }),
            new Paragraph({
                children: [new TextRun("   - 177次交易，胜率52.0%，总收益+$8,566.76")]
            }),
            new Paragraph({
                children: [new TextRun("   - 该策略专注于极端恐慌后的反转机会，在当前市场环境下表现稳定")]
            }),
            new Paragraph({ children: [] }),
            new Paragraph({
                children: [new TextRun({
                    text: "2. MACD 策略表现最差",
                    bold: true
                })]
            }),
            new Paragraph({
                children: [new TextRun("   - 10,796次交易，胜率46.4%，总亏损-$316,766.79")]
            }),
            new Paragraph({
                children: [new TextRun("   - 作为趋势跟踪策略，在震荡市场中频繁产生假信号")]
            }),
            new Paragraph({ children: [] }),
            new Paragraph({
                children: [new TextRun({
                    text: "3. 止损是主要亏损来源",
                    bold: true
                })]
            }),
            new Paragraph({
                children: [new TextRun("   - 止损平仓4,272次，亏损-$4,444,752.94")]
            }),
            new Paragraph({
                children: [new TextRun("   - 追踪止盈7,872次，盈利+$3,857,034.15")]
            }),
            new Paragraph({
                children: [new TextRun("   - 建议优化止损位置或降低仓位")]
            }),
            new Paragraph({ children: [] }),
            new Paragraph({
                children: [new TextRun({
                    text: "4. 整体亏损原因分析",
                    bold: true
                })]
            }),
            new Paragraph({
                children: [new TextRun("   - 高杠杆(50x)放大了止损的影响")]
            }),
            new Paragraph({
                children: [new TextRun("   - 策略信号过于频繁，导致过度交易")]
            }),
            new Paragraph({
                children: [new TextRun("   - 建议：降低杠杆、增加信号过滤条件、优化仓位管理")]
            }),
        ]
    }]
});

Packer.toBuffer(doc).then(buffer => {
    fs.writeFileSync('/sessions/6a0ae70048b42c882f2ed38f/workspace/全策略回测报告_2025_2026.docx', buffer);
    console.log('报告已生成: /sessions/6a0ae70048b42c882f2ed38f/workspace/全策略回测报告_2025_2026.docx');
});
