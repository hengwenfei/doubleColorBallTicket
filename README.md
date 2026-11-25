# 双色球选号与历史统计

一个使用 Python 标准库的本地桌面小工具，包含纯随机选号、历史频次加权选号和历史开奖统计。频次加权是可解释的娱乐性选号规则，不是有效的开奖结果预测，也不代表能够提高中奖概率。

## 运行

需要安装 Python 3，并确保当前 Python 带有 Tkinter：

```powershell
py ssq_tool.py
```

无需安装第三方依赖。

## 同步或导入历史数据

在“历史统计”页点击“联网同步官网开奖”，工具会从[中国福利彩票官网](https://www.cwl.gov.cn/)获取双色球历史开奖数据，显示最近一期号码，并据此更新频次统计与图表。联网同步失败时，可以改用“导入开奖 CSV”。

先同步或导入数据后，即可使用“按历史频次生成”。导入的 CSV 需要按时间从旧到新排列，最后一条有效记录会显示为最近一期。文件需要包含以下列名，列顺序不限；可以额外包含日期等列：

```csv
date,red1,red2,red3,red4,red5,red6,blue
2026-01-01,1,2,3,4,5,6,7
```

每行应为一期开奖：6 个不重复的红球（1–33）和 1 个蓝球（1–16）。CSV 导入结果以及官网同步结果都会统计每个号码的出现期数，并以柱状图展示红球、蓝球次数和各自均值。加权选号按“出现期数 + 1”作为抽取权重，红球不重复抽取。每注号码下方会说明生成方式及所选号码在当前数据中的出现次数。未出现过的号码仍有机会入选。

双色球每期开奖相互独立，历史频次不会改变下一期开奖的真实概率。频次加权只改变工具如何挑选号码，不应被视作提高中奖机会的方法。

## 运行测试

```powershell
py -m unittest -v
```

## 打包 Windows 安装程序

在 Windows 上安装 Python 3（需包含 `venv`）和 [Inno Setup 6](https://jrsoftware.org/isinfo.php)，在项目目录运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
```

脚本会在 `.build-venv` 中安装 PyInstaller，并在 `dist` 目录生成独立 exe 和 `双色球选号工具-Setup.exe` 安装程序。首次打包需要联网下载 PyInstaller。只生成 exe（不需要安装 Inno Setup）：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1 -ExeOnly
```
