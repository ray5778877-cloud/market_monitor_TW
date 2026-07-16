#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backtest_2.py — Alpha Score v11.2 NBR 籌碼大腦 歷史回測
==========================================================
資料清洗修正（Millennium 級審計）：
  ① 標的池對齊上市(.TW) / 上櫃(.TWO) 正確後綴，剔除下市殭屍股
  ② is_tradeable() / fx_rate() / _tw_code() 全面支援 .TWO
  ③ _is_tw 判斷式在所有量能 / 法人計算函式中統一修正
  ④ build_signal_frames 加入「缺檔保險大腦」：
       net_buy_df 不存在時自動退回 Volume-Barra，防止步進函數 Z-Score 數值爆炸
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
import time
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────────────
# 產業配置（上市 .TW / 上櫃 .TWO 後綴精確對齊，已剔除下市殭屍股）
# ─────────────────────────────────────────────────────────────────────────
INDUSTRIES: dict[str, list[str]] = {
    "AI 伺服器組裝":         ["2317.TW", "6669.TW", "2376.TW", "2382.TW", "3231.TW", "4938.TW", "2356.TW", "3706.TW", "2353.TW", "3017.TW", "8050.TWO", "7711.TWO"],
    "矽晶圓":                ["6488.TWO", "6182.TWO", "3016.TW", "3105.TWO", "5483.TWO", "3532.TW"],
    "液冷散熱":              ["3324.TWO", "3017.TW", "8261.TW", "6276.TWO", "2421.TW", "6230.TW", "3653.TW", "3338.TW"],
    "PCB 載板":              ["3037.TW", "8046.TW", "3189.TW", "6213.TW", "3149.TW", "8213.TW", "2367.TW", "3044.TW", "6201.TW", "6155.TW", "6141.TWO", "6224.TW", "3294.TWO", "3021.TW"],
    "被動元件 MLCC":          ["2327.TW", "2492.TW", "2375.TW", "2438.TW", "6112.TWO", "2456.TW", "5349.TWO", "3144.TWO", "2437.TW", "4999.TWO", "5222.TWO", "6194.TWO", "6126.TWO", "6173.TWO", "6158.TWO", "6259.TWO", "6266.TWO", "6407.TWO", "5328.TWO", "6210.TWO", "3026.TW"],
    "功率電感":              ["6147.TWO", "6285.TW", "3094.TWO", "3533.TW", "2456.TW", "3068.TW", "2350.TW", "2452.TW", "6175.TW", "3593.TW"],
    "電容器":                ["2375.TW", "2438.TW", "6276.TWO", "2327.TW", "2456.TW", "6112.TWO", "2492.TW", "3089.TWO", "3465.TWO", "6204.TWO", "2472.TW", "3026.TW"],
    "電阻與被動保護":          ["2342.TW", "1781.TWO", "3042.TW", "2492.TW", "2327.TW", "6271.TW", "5291.TWO", "6862.TWO", "6940.TWO", "6913.TWO", "3631.TW"],
    "NOR Flash 利基記憶體":    ["2344.TW", "5351.TWO", "2337.TW", "8261.TW", "3014.TW", "8104.TWO", "8054.TW", "8299.TWO", "3006.TWO"],
    "記憶體模組":            ["2408.TW", "5269.TW", "5388.TWO", "2344.TW", "3260.TWO", "2451.TW", "3661.TW", "9102.TW", "3474.TW", "2396.TW", "5289.TWO", "4967.TW", "4973.TWO", "5469.TW", "8271.TWO", "3317.TWO", "3265.TWO"],
    "HBM 高頻寬記憶體":        ["2408.TW", "2344.TW", "5269.TW", "5388.TWO", "2330.TW", "3711.TW", "6515.TW"],
    "高速光模組":            ["3081.TWO", "4979.TW", "8121.TWO", "4906.TW", "6177.TWO", "3450.TW", "6243.TW", "6588.TWO", "6207.TWO", "7717.TWO", "3234.TWO", "3303.TWO"],
    "客製 ASIC 矽智財":       ["3661.TW", "3443.TW", "6533.TW", "2454.TW", "3035.TW", "5269.TW", "6643.TWO", "3529.TWO"],
    "HPC 與網通 IC":         ["2454.TW", "2379.TW", "2345.TW", "5274.TW", "3035.TW", "6286.TW", "3014.TW", "6485.TWO", "5236.TWO", "5272.TWO", "6532.TWO", "6548.TWO", "4968.TW", "6563.TWO", "6152.TW", "6104.TWO", "6229.TWO", "6237.TWO", "8086.TWO", "6788.TWO"],
    "CPU 與 Agentic AI":     ["2330.TW", "2454.TW", "3443.TW", "3661.TW", "5347.TWO", "3035.TW", "2379.TW", "6515.TW"],
    "Edge AI AIoT":          ["2454.TW", "3443.TW", "6669.TW", "2345.TW", "3014.TW", "2379.TW", "3661.TW", "6515.TW", "4980.TWO", "6579.TW", "6414.TW", "8234.TW", "7455.TWO", "4925.TWO", "3227.TWO"],
    "第三代半導體":          ["3707.TW", "3016.TW", "6789.TW", "3105.TWO", "6443.TW", "5346.TW", "5269.TW", "8199.TWO", "3214.TWO", "3061.TW", "5425.TW", "8028.TW", "7770.TWO", "6927.TWO", "6920.TWO"],
    "矽光子與 CPO":          ["3105.TWO", "3081.TWO", "8121.TWO", "4979.TW", "3450.TW", "6243.TW", "2454.TW", "3037.TW"],
    "顯示驅動 IC":           ["3034.TW", "3014.TW", "2363.TW", "5471.TW", "3257.TWO", "3094.TWO", "5280.TW", "6462.TWO", "5248.TWO", "4995.TWO", "4966.TW", "4961.TW", "6151.TW", "5489.TW", "5484.TW", "8016.TW", "8111.TW", "6775.TW", "6962.TW", "2426.TW"],
    "面板產業":              ["2409.TW", "3481.TW", "6116.TW", "3149.TW", "3504.TW", "2406.TW", "3009.TW", "2384.TW", "2475.TW", "6289.TW", "3383.TW", "2499.TW", "5245.TW", "6176.TW", "5371.TW", "6225.TWO", "8069.TWO", "6682.TWO", "4942.TW", "3630.TWO"],
    "MicroLED 顯示供應鏈":   ["6116.TW", "2409.TW", "3481.TW", "3406.TW", "3008.TW", "2448.TW", "3504.TW", "6854.TW", "6111.TWO", "3615.TWO", "3535.TW"],
    "光學鏡頭":              ["3008.TW", "2392.TW", "3406.TW", "6789.TW", "4977.TW", "6271.TW", "5306.TW", "5281.TW", "9106.TW", "6131.TWO", "5259.TWO", "5240.TWO", "5230.TWO", "4949.TW", "6556.TWO", "6559.TWO", "6517.TWO", "5392.TWO", "6209.TW", "6120.TW"],
    "光感測與元件":          ["6789.TW", "6271.TW", "3105.TWO", "3406.TW", "2448.TW", "5347.TWO", "3661.TW", "3627.TWO", "3080.TWO", "2494.TW", "5277.TWO", "3698.TWO", "6419.TWO", "5251.TWO", "5267.TWO", "6434.TW", "6560.TWO", "6498.TWO", "5220.TWO", "6477.TW"],
    "AI PC 筆電與平板":      ["2357.TW", "2376.TW", "4938.TW", "2353.TW", "2454.TW", "2382.TW", "3017.TW", "2356.TW", "2474.TW", "3706.TW", "2324.TW", "2377.TW", "2425.TW", "2301.TW", "2364.TW", "2365.TW", "2352.TW", "3673.TW", "3611.TW", "3625.TW"],
    "智慧型手機":            ["2317.TW", "2354.TW", "2392.TW", "4938.TW", "3231.TW", "3008.TW", "3406.TW", "2474.TW", "2356.TW"],
    "EMS 電子代工":          ["2317.TW", "2354.TW", "2382.TW", "4938.TW", "3231.TW", "2356.TW", "2308.TW", "6285.TW", "3706.TW", "2429.TW", "2459.TW", "2340.TW", "2361.TW", "3053.TW", "2341.TW", "2336.TW", "2315.TW", "2446.TW", "3367.TW", "4994.TW"],
    "封測代工":              ["3711.TW", "2449.TW", "6147.TWO", "8150.TWO", "3680.TW", "2369.TW", "2329.TW", "6271.TW", "2325.TW", "2311.TW", "6435.TW", "6205.TW", "6278.TW", "6261.TWO", "6409.TW", "6291.TWO", "6257.TWO", "6239.TW", "2441.TW", "3583.TW"],
    "AI 先進封裝":           ["3711.TW", "8150.TWO", "3680.TW", "2449.TW", "3131.TWO", "6147.TWO", "2330.TW", "6243.TW", "3037.TW", "3259.TWO"],
    "晶圓代工":              ["2330.TW", "2303.TW", "5347.TWO", "6770.TW", "3707.TW", "3035.TW", "6515.TW", "7828.TWO", "2323.TW", "3372.TW", "3059.TW"],
    "晶圓廠設備":            ["3680.TW", "3131.TWO", "8027.TW", "3563.TW", "6191.TW", "4749.TW", "6196.TW", "6139.TW", "6223.TWO", "3413.TW"],
    "前段製程材料":          ["6147.TWO", "8121.TWO", "4763.TWO", "3691.TW", "3128.TWO", "5234.TW", "5302.TW", "5297.TWO", "4960.TW", "6134.TW", "5434.TW", "6283.TWO", "7887.TWO", "7918.TWO", "8131.TW", "8215.TW", "6698.TW", "6967.TWO", "3467.TW", "3374.TW"],
    "前段製程設備":          ["3680.TW", "8027.TW", "3131.TWO", "3563.TW", "6191.TW"],
    "封裝量測自動化":        ["3680.TW", "3131.TWO", "6671.TWO", "3563.TW", "6191.TW", "3017.TW", "2479.TW", "6510.TW", "2444.TW", "2423.TW", "2360.TW", "3455.TW", "2467.TW", "3162.TW", "3276.TW"],
    "封裝製程機台":          ["3680.TW", "8027.TW", "6671.TWO", "3131.TWO", "6191.TW", "3563.TW", "5443.TW", "6136.TW", "6128.TW", "6272.TW", "6215.TW", "6640.TW", "2404.TW", "2464.TW"],
    "日本前段設備":          ["3680.TW", "8027.TW", "3131.TWO", "6191.TW"],
    "日本後段設備":          ["3680.TW", "3131.TWO", "6671.TWO", "6191.TW"],
    "日本被動元件":          ["2327.TW", "2492.TW", "2375.TW", "2438.TW", "6112.TWO", "2456.TW"],
    "日本矽晶圓":            ["6488.TWO", "3105.TWO", "6182.TWO", "3016.TW", "5483.TWO", "3532.TW"],
    "石英頻率控制":          ["3042.TW", "5471.TW", "6271.TW", "3094.TWO", "6147.TWO", "2456.TW", "8078.TW", "2485.TW"],
    "AI 互連元件":           ["3533.TW", "2392.TW", "6669.TW", "3023.TW", "6177.TWO", "3015.TW", "6280.TW", "6185.TW", "6290.TW", "3646.TW"],
    "連接器 工業消費":       ["2392.TW", "3533.TW", "6177.TWO", "3023.TW", "2313.TW", "3030.TW", "6271.TW", "5383.TW", "6422.TW", "6584.TW", "5228.TWO", "6418.TW", "5254.TW", "6432.TW", "6573.TW", "6192.TW", "6124.TW", "6133.TW", "6279.TW", "6292.TW"],
    "車用連接器":            ["2392.TW", "6177.TWO", "3023.TW", "3533.TW", "2313.TW", "3030.TW", "2308.TW", "2241.TW", "7732.TW", "6288.TW", "1533.TW", "4581.TW", "3346.TW"],
    "軟板":                  ["8155.TW", "6213.TW", "3023.TW", "3138.TW", "3045.TW", "3150.TW", "1585.TW", "6251.TW", "4958.TW", "6153.TW", "6156.TW", "6269.TW", "8039.TW", "2383.TW", "3715.TW", "3390.TW", "4927.TW", "3296.TW", "3027.TW"],
    "PCB 硬板製造":          ["3037.TW", "8046.TW", "3189.TW", "6213.TW", "3149.TW", "8213.TW", "2316.TW", "2367.TW", "3044.TW", "5243.TW", "6426.TW", "5285.TW", "6538.TW", "6197.TW", "5536.TW", "6274.TW", "5439.TW", "6284.TW", "5493.TW", "8038.TW", "2368.TW"],
    "玻璃基板":              ["8033.TW", "3149.TW", "6116.TW", "6213.TW", "3504.TW", "1802.TW"],
    "玻纖布":                ["1717.TW", "1710.TW", "1773.TW", "1605.TW", "1303.TW", "1301.TW"],
    "導線架與化學品":        ["2342.TW", "4763.TWO", "8121.TWO", "3128.TWO", "1722.TW", "3691.TW", "1781.TW"],
    "電池關鍵材料":          ["1722.TW", "4763.TWO", "3128.TWO", "3691.TW", "5227.TWO", "1503.TW", "3576.TW", "6495.TW", "6555.TW", "7758.TW", "6990.TW", "6883.TW", "1537.TW", "3191.TW"],
    "電芯製造與電池模組":    ["3576.TW", "3211.TW", "5227.TWO", "4943.TW", "1722.TW", "6121.TW", "6558.TW"],
    "BBU 電池備援":          ["4931.TW", "3211.TW", "3023.TW", "6412.TW", "3015.TW", "3017.TW", "5227.TWO"],
    "儲能系統整合":          ["1519.TW", "2308.TW", "4943.TW", "3576.TW", "6443.TW", "3015.TW", "6121.TW", "5227.TWO", "1503.TW"],
    "電源供應器":            ["2308.TW", "6412.TW", "3015.TW", "3017.TW", "3211.TW", "1519.TW", "6431.TW", "2418.TW", "6512.TW", "6184.TW", "6114.TW", "5309.TW", "5488.TW", "5457.TW", "3628.TW", "3484.TW", "4588.TW", "2460.TW", "2462.TW", "3322.TW"],
    "電器電纜":              ["1604.TW", "1605.TW", "1614.TW", "1503.TW", "1519.TW", "1513.TW", "1626.TW", "1612.TW", "1601.TW", "1606.TW", "1613.TW", "5244.TW", "5283.TW", "8107.TW", "8109.TW", "1526.TW", "1603.TW", "1608.TW", "1609.TW", "1611.TW"],
    "氣冷與核心組件":        ["3017.TW", "3324.TW", "8261.TW", "2421.TW", "3015.TW", "6230.TW", "3653.TW", "3338.TW", "3043.TW"],
    "整合與委外":            ["2308.TW", "2317.TW", "3231.TW", "4938.TW", "2382.TW", "2356.TW", "2354.TW", "6669.TW", "3706.TW"],
    "雲端與 MSP":            ["6669.TW", "6690.TW", "2382.TW", "3687.TW", "6165.TW", "5321.TW", "5287.TW", "5278.TW", "3130.TW", "6689.TW", "6811.TW", "2640.TW", "6404.TW", "6997.TW", "7714.TW", "6163.TW", "6236.TW", "6473.TW", "6590.TW", "6565.TW"],
    "企業 SaaS":             ["6669.TW", "8155.TW", "6690.TW", "6183.TW", "5478.TW", "5202.TW", "2417.TW", "6763.TW", "6865.TW", "6902.TW", "2447.TW", "6925.TW", "7738.TW", "6910.TW", "4953.TW", "6536.TW", "5211.TW", "6140.TW", "6214.TW", "6231.TW"],
    "資安防護":              ["6690.TW", "6183.TW", "5274.TW", "6533.TW", "5212.TW", "2419.TW", "2345.TW", "6123.TW", "5201.TW", "5210.TW", "7765.TW", "7823.TW", "6868.TW"],
    "CXL 技術":              ["2454.TW", "2344.TW", "8261.TW", "5269.TW", "2408.TW", "5388.TW", "6515.TW", "3035.TW"],
    "AR VR XR 光學":         ["3008.TW", "2392.TW", "3406.TW", "3081.TW", "2448.TW", "5306.TW", "4977.TW", "6271.TW"],
    "電商零售":              ["8044.TW", "2722.TW", "2912.TW", "2723.TW", "2727.TW", "5904.TW", "2929.TW", "6741.TW", "8477.TW", "8472.TW", "3085.TW", "5903.TW", "8454.TW", "8443.TW"],
    "低軌衛星":              ["3491.TW", "2313.TW", "4906.TW", "6285.TW", "2419.TW", "3380.TW"],
    "高速交換器與無線網路":  ["2345.TW", "6285.TW", "3380.TW", "2332.TW", "3491.TW", "6514.TW", "2391.TW", "6403.TW", "3682.TW", "6470.TW", "6417.TW", "6530.TW", "6190.TW", "6161.TW", "6277.TW", "8071.TW", "3632.TW", "3596.TW", "3447.TW", "3025.TW", "3221.TW"],
    "離岸風電":              ["1519.TW", "1503.TW", "6443.TW", "3576.TW", "6753.TW", "1513.TW", "1626.TW", "2206.TW", "3708.TW", "2072.TW", "7786.TW", "9958.TW", "6793.TW", "7583.TW", "7702.TW", "3712.TW"],
    "太陽能產業":            ["6443.TW", "3576.TW", "3691.TW", "5227.TW", "3514.TW", "3519.TW", "6806.TW", "3599.TW", "3561.TW", "6244.TW", "6839.TW", "6692.TW", "6987.TW", "6994.TW", "6977.TW", "6887.TW", "6944.TW", "6946.TW", "6947.TW", "1529.TW"],
    "工業自動化":            ["2049.TW", "4526.TW", "3563.TW", "1597.TW", "2059.TW", "3017.TW", "1589.TW", "1507.TW", "1532.TW", "1535.TW", "1560.TW", "1580.TW", "1590.TW", "2395.TW", "3594.TW", "4532.TW", "4543.TW", "4563.TW", "4580.TW", "3088.TW"],
    "CNC 工具機":            ["2049.TW", "4526.TW", "1597.TW", "3563.TW", "1583.TW", "1530.TW", "2374.TW", "6609.TW", "4587.TW", "3167.TW"],
    "精密機構件":            ["2049.TW", "6147.TW", "3563.TW", "3680.TW", "2474.TW", "1597.TW", "3338.TW", "2059.TW", "4578.TW", "1563.TW", "2254.TW", "2258.TW", "6983.TW", "6833.TW", "6603.TW", "6604.TW", "6606.TW", "6705.TW", "6727.TW", "7704.TW"],
    "機殼與滑軌":            ["2474.TW", "3017.TW", "1597.TW", "2354.TW", "3653.TW", "3338.TW", "6903.TW", "6115.TW", "6117.TW", "3693.TW", "3540.TW", "2491.TW"],
    "石化與塑膠產業":        ["1301.TW", "1303.TW", "1326.TW", "6505.TW", "1304.TW", "1313.TW", "1710.TW", "1717.TW", "1722.TW", "1711.TW", "1714.TW", "1718.TW", "1721.TW", "1305.TW", "1309.TW", "1323.TW", "1325.TW", "4721.TW", "4722.TW", "1715.TW"],
    "資源環保工業":          ["2503.TW", "1417.TW", "8011.TW", "3691.TW", "1503.TW", "1519.TW", "6641.TW", "8473.TW", "8341.TW", "6581.TW", "9930.TW", "8422.TW", "9955.TW", "6624.TW", "6803.TW", "8423.TW", "8476.TW", "5205.TW", "5432.TW", "6969.TW", "7610.TW"],
    "貨櫃航運":              ["2603.TW", "2609.TW", "2615.TW", "2637.TW", "2605.TW", "2618.TW", "5607.TW", "5601.TW", "7863.TW", "8367.TW", "2607.TW", "2608.TW", "2610.TW", "2611.TW", "2612.TW", "2613.TW", "2630.TW", "2636.TW", "2641.TW", "2642.TW"],
    "散裝航運":              ["2606.TW", "5608.TW", "2637.TW", "2645.TW", "2615.TW", "2617.TW", "2206.TW", "2208.TW", "2601.TW", "5609.TW", "5603.TW", "7716.TW", "2646.TW", "2643.TW"],
    "銀行金融":              ["2881.TW", "2882.TW", "2891.TW", "2880.TW", "2884.TW", "2885.TW", "2886.TW", "2887.TW", "2890.TW", "2892.TW", "2883.TW", "2888.TW", "2889.TW", "2801.TW", "2809.TW", "2812.TW", "2823.TW", "5876.TW", "5880.TW"],
    "IC 通路":               ["3036.TW", "2455.TW", "3047.TW", "2347.TW", "3094.TWO", "6125.TW", "8081.TW", "3526.TW", "2403.TW", "3315.TW", "6145.TW", "6189.TW", "6154.TW", "8067.TW", "8068.TW", "8070.TW", "3702.TW", "3709.TW", "3444.TW", "3528.TW"],
    "IC 測試服務":           ["6271.TW", "3680.TW", "3131.TWO", "2449.TW", "3705.TW", "6243.TW", "6255.TW", "4951.TW", "4971.TW", "6174.TW", "6217.TW", "7856.TW", "6786.TW", "3587.TW", "3264.TW", "3289.TW"],
    "類比與功率 IC":         ["6271.TW", "5274.TW", "3034.TW", "3014.TW", "8081.TW", "6202.TW", "3526.TW", "3063.TW", "8162.TW", "6451.TW", "5299.TW", "5262.TW", "6568.TW", "6103.TW", "6146.TW", "6138.TW", "6411.TW", "5487.TW", "6233.TW", "8021.TW"],
    "國防軍工":              ["8033.TW", "2645.TW", "6753.TW", "3491.TW", "2206.TW", "1597.TW", "2634.TW"],
    "連接元件":              ["3665.TW", "3605.TW", "3533.TW", "3526.TWO", "3023.TW"],
}

# ─────────────────────────────────────────────────────────────────────────
# 常數
# ─────────────────────────────────────────────────────────────────────────
BENCHMARK         = "SOXX"
BACKTEST_START    = dt.date(2026, 1, 1)
BACKTEST_END      = dt.date.today()
WARMUP_DAYS       = 100

MA_SHORT          = 20
MOM_WINDOW        = 5
POC_LOOKBACK      = 60
DZ_LOOKBACK       = 20
HH_LOOKBACK       = 60
SWING_N           = 5

ENTRY_PCT              = 0.85
MAX_POSITIONS          = 10
STOCKS_PER_SIGNAL      = 2
STOP_LOSS_PCT          = 0.08
MIN_HOLD_BARS          = 5
TRAILING_TRIGGER_PCT   = 0.15
TRAILING_STOP_PCT      = 0.15
CLUSTER_WARNING_N      = 6
INIT_CAPITAL      = 100_000.0
BATCH_SIZE        = 8

USD_TWD = 32.0
USD_JPY = 155.0
USD_KRW = 1350.0

NET_BUY_CSV = "data/net_buy_shares.csv"
PORTFOLIO_JSON = "data/latest_portfolio.json"

ALL_TICKERS: list[str] = sorted(
    {BENCHMARK, "^VIX"} | {t for tks in INDUSTRIES.values() for t in tks}
)


# ─────────────────────────────────────────────────────────────────────────
# 工具函式（全面支援 .TW / .TWO 雙後綴）
# ─────────────────────────────────────────────────────────────────────────
def is_tradeable(sym: str) -> bool:
    """允許台股（.TW / .TWO）；排除日股 .T、韓股 .KS 及無後綴美股。"""
    return sym.endswith(".TW") or sym.endswith(".TWO")


def fx_rate(sym: str) -> float:
    if sym.endswith(".TW") or sym.endswith(".TWO"): return USD_TWD
    if sym.endswith(".T"):  return USD_JPY
    if sym.endswith(".KS"): return USD_KRW
    return 1.0


def _tw_code(sym: str) -> str:
    """相容上市(.TW)與上櫃(.TWO)後綴，切出純數字代碼（用於查詢 net_buy_df 欄位）。
    Bug fix：舊 sym[:-3] 對 .TWO 會切出帶小數點的錯誤代碼，已修正為依後綴長度切割。
    """
    if sym.endswith(".TW"):  return sym[:-3]   # "2330.TW"  → "2330"
    if sym.endswith(".TWO"): return sym[:-4]   # "3105.TWO" → "3105"
    return sym


def _bar(done: int, total: int, width: int = 30) -> str:
    filled = int(width * done / max(total, 1))
    return f"[{'█'*filled}{'░'*(width-filled)}] {done}/{total}"


def _is_tw_sym(sym: str) -> bool:
    """True 若為台灣市場標的（上市 .TW 或上櫃 .TWO）。"""
    return sym.endswith(".TW") or sym.endswith(".TWO")


# ─────────────────────────────────────────────────────────────────────────
# 台股量能自適應補償過濾器
# ─────────────────────────────────────────────────────────────────────────
def clamp_taiwan_volume(
    close_series: pd.Series,
    vol_series: pd.Series,
    is_tw: bool,
) -> pd.Series:
    if not is_tw:
        return vol_series
    avg20  = vol_series.rolling(20, min_periods=5).mean()
    avg5   = vol_series.rolling(5,  min_periods=1).mean()
    ma5_c  = close_series.rolling(5, min_periods=1).mean()
    upper  = (avg20 * 5.0).fillna(vol_series)
    clamped = vol_series.clip(upper=upper)
    disposition = (avg5 < avg20 * 0.25) & (close_series > ma5_c)
    compensated = avg20 * 1.2
    clamped     = clamped.where(~disposition, other=compensated)
    return clamped.fillna(vol_series)


# ─────────────────────────────────────────────────────────────────────────
# 數據下載
# ─────────────────────────────────────────────────────────────────────────
def download_all(start: dt.date, end: dt.date) -> dict[str, pd.DataFrame]:
    start_s = start.isoformat()
    end_s   = (end + dt.timedelta(days=1)).isoformat()
    result: dict[str, pd.DataFrame] = {}
    batches = [ALL_TICKERS[i: i + BATCH_SIZE] for i in range(0, len(ALL_TICKERS), BATCH_SIZE)]
    n = len(batches)

    for bi, batch in enumerate(batches, 1):
        sys.stdout.write(f"\r  {_bar(bi, n)}  ")
        sys.stdout.flush()
        try:
            raw = yf.download(
                batch, start=start_s, end=end_s,
                interval="1d", group_by="ticker",
                auto_adjust=True, progress=False, threads=True,
            )
            if raw is None or raw.empty:
                raise ValueError("empty")
            for sym in batch:
                try:
                    cols = raw.columns
                    if isinstance(cols, pd.MultiIndex):
                        l0 = cols.get_level_values(0)
                        df = (raw[sym].copy() if sym in l0
                              else raw.xs(sym, axis=1, level=1).copy())
                    else:
                        df = raw.copy()
                    df = df.rename(columns=str.title)
                    for c in ("Open", "High", "Low", "Close", "Volume"):
                        if c not in df.columns:
                            df[c] = np.nan
                    idx = pd.to_datetime(df.index)
                    df.index = (idx.tz_localize("UTC")
                                if idx.tz is None else idx.tz_convert("UTC"))
                    df = df.sort_index().loc[~df.index.duplicated(keep="last")]
                    df[["Open", "High", "Low", "Close"]] = (
                        df[["Open", "High", "Low", "Close"]].ffill()
                    )
                    df["Volume"] = df["Volume"].fillna(0)
                    if df["Close"].notna().sum() > 15:
                        df["VolumeUSD"] = df["Close"] * df["Volume"] / fx_rate(sym)
                        result[sym] = df
                except Exception:
                    pass
        except Exception:
            pass
        time.sleep(0.35)

    print(f"\r  完成：{len(result)}/{len(ALL_TICKERS)} 個標的有效            ")
    return result


# ─────────────────────────────────────────────────────────────────────────
# 三大法人淨買超資料載入
# ─────────────────────────────────────────────────────────────────────────
def load_net_buy_csv(path: str = NET_BUY_CSV) -> pd.DataFrame | None:
    """
    載入 data/net_buy_shares.csv。
    格式：索引=Date(UTC)，欄位=純數字代碼（如 "2330" / "3105"），值=當日淨買超股數。
    若檔案不存在，回傳 None（系統自動退回 Volume-Barra 保險大腦）。
    """
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    else:
        df.index = df.index.tz_convert("UTC")
    df = df.sort_index()
    return df


def _nb_usd_series(
    sym: str,
    close_s: pd.Series,
    vol_s: pd.Series,
    calendar: pd.DatetimeIndex,
    net_buy_df: pd.DataFrame | None,
) -> pd.Series:
    """
    計算個股「法人淨買超金額（USD 等值）」時間序列。

    台股（.TW / .TWO）：直接讀取 net_buy_df[code] × Close / fx_rate
    非台股              ：近似為 Volume × 0.15 × sign(1d_return)
    """
    _is_tw = _is_tw_sym(sym)
    if _is_tw and net_buy_df is not None:
        code = _tw_code(sym)
        if code in net_buy_df.columns:
            nb_shares = net_buy_df[code].reindex(calendar).ffill().fillna(0)
        else:
            nb_shares = pd.Series(0.0, index=calendar)
    else:
        ret_1d    = close_s.pct_change().fillna(0)
        sign_ret  = np.sign(ret_1d).replace(0.0, 1.0)
        nb_shares = vol_s * 0.15 * sign_ret

    return (nb_shares * close_s / fx_rate(sym)).fillna(0)


# ─────────────────────────────────────────────────────────────────────────
# 產業面板（Top-2 龍頭動能加權 + NBR 籌碼大腦）
# ─────────────────────────────────────────────────────────────────────────
def build_industry_panel(
    panels: dict[str, pd.DataFrame],
    net_buy_df: pd.DataFrame | None = None,
) -> dict[str, pd.DataFrame]:
    result: dict[str, pd.DataFrame] = {}

    for ind, tickers in INDUSTRIES.items():
        available = [t for t in tickers if t in panels]
        if not available:
            continue

        all_dates = sorted({ts for t in available for ts in panels[t].index.tolist()})
        calendar  = pd.DatetimeIndex(all_dates)

        close_cols:    dict[str, pd.Series] = {}
        vol_cols:      dict[str, pd.Series] = {}
        net_buy_cols:  dict[str, pd.Series] = {}

        for sym in available:
            df = panels[sym].reindex(calendar)
            df[["Open", "High", "Low", "Close"]] = df[["Open", "High", "Low", "Close"]].ffill()
            df["Volume"] = df["Volume"].fillna(0)
            _is_tw = _is_tw_sym(sym)    # ← 支援 .TW / .TWO
            df["Volume"] = clamp_taiwan_volume(df["Close"], df["Volume"], _is_tw)
            df["VolumeUSD"] = df["Close"] * df["Volume"] / fx_rate(sym)

            close_s = df["Close"].ffill()
            if df["Close"].dropna().empty:
                continue

            close_cols[sym]   = close_s
            vol_cols[sym]     = df["VolumeUSD"].fillna(0)
            net_buy_cols[sym] = _nb_usd_series(
                sym, close_s, df["Volume"], calendar, net_buy_df
            )

        if not close_cols:
            continue

        closes   = pd.concat(close_cols.values(),   axis=1, keys=close_cols.keys())
        volumes  = pd.concat(vol_cols.values(),     axis=1, keys=vol_cols.keys())
        net_buys = pd.concat(net_buy_cols.values(), axis=1, keys=net_buy_cols.keys())

        ind_ret  = closes.pct_change()
        avg_vol  = volumes.rolling(MA_SHORT,   min_periods=MA_SHORT  ).mean().replace(0, np.nan)
        vol_sum5 = volumes.rolling(MOM_WINDOW, min_periods=MOM_WINDOW).sum()
        cum5     = (
            (1 + ind_ret)
            .rolling(MOM_WINDOW, min_periods=MOM_WINDOW)
            .apply(np.prod, raw=True) - 1
        )
        stock_vpmi5 = (vol_sum5 / (MOM_WINDOW * avg_vol)) * cum5 * 100.0

        TOP_N     = min(2, closes.shape[1])
        vpmi_rank = stock_vpmi5.rank(axis=1, ascending=False, na_option="bottom")
        top2_mask = vpmi_rank <= TOP_N
        all_nan   = stock_vpmi5.isna().all(axis=1)
        top2_mask.loc[all_nan] = True

        n_sel     = top2_mask.sum(axis=1).clip(lower=1)
        eq_return = (ind_ret   * top2_mask).sum(axis=1) / n_sel
        total_vol = (volumes   * top2_mask).sum(axis=1)
        eq_close  = (1 + eq_return.fillna(0)).cumprod() * 100.0

        all_total_vol = volumes.sum(axis=1)
        total_net_buy = net_buys.sum(axis=1)

        result[ind] = pd.DataFrame({
            "EqClose":     eq_close,
            "EqReturn":    eq_return,
            "TotalVol":    total_vol,
            "AllTotalVol": all_total_vol,
            "TotalNetBuy": total_net_buy,
        })

    return result


# ─────────────────────────────────────────────────────────────────────────
# 個股時間序列（台股 .TW / .TWO，含開盤報酬 + 法人淨買超）
# ─────────────────────────────────────────────────────────────────────────
def build_stock_frames(
    panels: dict[str, pd.DataFrame],
    net_buy_df: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    tradeable = sorted(
        sym for sym in panels
        if sym != BENCHMARK and is_tradeable(sym)
    )
    if not tradeable:
        empty = pd.DataFrame()
        return empty, empty, empty, empty, empty

    all_dates: list = []
    for sym in tradeable:
        all_dates.extend(panels[sym].index.tolist())
    calendar = pd.DatetimeIndex(sorted(set(all_dates)))

    min_bars    = MA_SHORT + MOM_WINDOW + 5
    ret_d:      dict[str, pd.Series] = {}
    vpmi_d:     dict[str, pd.Series] = {}
    open_ret_d: dict[str, pd.Series] = {}
    close_d:    dict[str, pd.Series] = {}
    nb_d:       dict[str, pd.Series] = {}

    for sym in tradeable:
        df_sym  = panels[sym].reindex(calendar)
        close   = df_sym["Close"].ffill()
        open_p  = df_sym["Open"].ffill()
        _raw_vol = df_sym["Volume"].fillna(0)
        _is_tw   = _is_tw_sym(sym)   # ← 支援 .TW / .TWO
        _vol_adj = clamp_taiwan_volume(close, _raw_vol, _is_tw)
        vol      = _vol_adj * close / fx_rate(sym)

        if close.notna().sum() < min_bars:
            continue

        vpmi = _vpmi5(close, vol)
        ret_d[sym]      = close.pct_change().fillna(0.0)
        vpmi_d[sym]     = vpmi.fillna(0.0)
        open_ret_d[sym] = (open_p / close.shift(1) - 1).fillna(0.0)
        close_d[sym]    = close
        nb_d[sym]       = _nb_usd_series(sym, close, _vol_adj, calendar, net_buy_df)

    return (
        pd.DataFrame(ret_d),
        pd.DataFrame(vpmi_d),
        pd.DataFrame(open_ret_d),
        pd.DataFrame(close_d),
        pd.DataFrame(nb_d),
    )


# ─────────────────────────────────────────────────────────────────────────
# VPMI_5D 計算
# ─────────────────────────────────────────────────────────────────────────
def _vpmi5(close: pd.Series, vol: pd.Series) -> pd.Series:
    avg_vol  = vol.rolling(MA_SHORT, min_periods=MA_SHORT).mean()
    vol_sum5 = vol.rolling(MOM_WINDOW, min_periods=MOM_WINDOW).sum()
    ret      = close.pct_change()
    cum5 = (1 + ret).rolling(MOM_WINDOW, min_periods=MOM_WINDOW).apply(
        lambda x: float(np.prod(x)) - 1.0, raw=True
    )
    return (vol_sum5 / (MOM_WINDOW * avg_vol.replace(0, np.nan))) * cum5 * 100.0


# ─────────────────────────────────────────────────────────────────────────
# 輔助指標函式
# ─────────────────────────────────────────────────────────────────────────
def _rolling_hist_pct_rank(series: pd.Series, lookback: int = 60) -> pd.Series:
    arr    = series.values.astype(float)
    n      = len(arr)
    result = np.full(n, np.nan)
    for i in range(n):
        lo     = max(0, i - lookback + 1)
        window = arr[lo: i + 1]
        valid  = window[~np.isnan(window)]
        if len(valid) < 3:
            result[i] = 50.0
            continue
        target = arr[i]
        result[i] = (50.0 if np.isnan(target)
                     else float((valid < target).sum()) / len(valid) * 100.0)
    return pd.Series(result, index=series.index)


def _donchian_position_series(eq_close: pd.Series, lookback: int = 60) -> pd.Series:
    cv     = eq_close.values.astype(float)
    n      = len(cv)
    result = np.full(n, np.nan)
    for i in range(lookback - 1, n):
        lo   = max(0, i - lookback + 1)
        w    = cv[lo: i + 1]
        lo_v = w.min(); hi_v = w.max()
        result[i] = 50.0 if hi_v <= lo_v else (cv[i] - lo_v) / (hi_v - lo_v) * 100.0
    return pd.Series(result, index=eq_close.index)


def _ma_spread_pct_rank_series(
    eq_close: pd.Series,
    short: int = 20,
    long_: int = 50,
    lookback: int = 60,
) -> pd.Series:
    ma_s   = eq_close.rolling(short,  min_periods=short ).mean()
    ma_l   = eq_close.rolling(long_,  min_periods=long_ ).mean()
    spread = (ma_s - ma_l) / ma_l.replace(0, np.nan)
    return _rolling_hist_pct_rank(spread.fillna(0.0), lookback=lookback)


# ─────────────────────────────────────────────────────────────────────────
# 產業層級 Alpha Score 信號矩陣（NBR 籌碼大腦 + 缺檔保險退回）
# ─────────────────────────────────────────────────────────────────────────
def build_signal_frames(
    ind_panel: dict[str, pd.DataFrame],
    net_buy_available: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Alpha Score v11.2 NBR 籌碼大腦信號引擎。

    net_buy_available=True  → NBR Z-Score Barra（法人籌碼驅動）
    net_buy_available=False → Volume Z-Score Barra（自動退回，防止步進函數數值爆炸）

    「缺檔保險大腦」啟動條件：
      - data/net_buy_shares.csv 不存在
      - 此時 TotalNetBuy ≈ Volume × 0.15 × sign(ret)，方差極低
      - sigma_20_nbr → 0，Z-Score 除法爆炸 → Alpha 評分完全失真
      → 系統偵測到此狀況後自動退回 Volume-Barra 保持完整功能
    """
    inds   = list(ind_panel.keys())
    hpct_d = {}
    vp_d   = {}
    ms_d   = {}
    vpmi_d = {}
    dev50_d= {}

    print(f"  計算 Alpha v11.2 信號時間序列 ({len(inds)} 個產業)...")
    for k, ind in enumerate(inds, 1):
        sys.stdout.write(f"\r  {_bar(k, len(inds))}  ")
        sys.stdout.flush()
        df  = ind_panel[ind]
        eq  = df["EqClose"]
        vol = df["TotalVol"]

        vpmi        = _vpmi5(eq, vol)
        vpmi_d[ind] = vpmi

        ma20_eq      = eq.rolling(20, min_periods=10).mean()
        ma50_eq      = eq.rolling(50, min_periods=25).mean()
        dev50_d[ind] = (
            (ma20_eq - ma50_eq) / ma50_eq.replace(0, np.nan) * 100.0
        ).fillna(0.0)

        vp_d[ind] = _donchian_position_series(eq, lookback=POC_LOOKBACK)
        ms_d[ind] = _ma_spread_pct_rank_series(eq, short=20, long_=50, lookback=60)

        # ── 缺檔偵測：若 net_buy_available=False 或 AllTotalVol 全零，退回 Volume Barra ──
        nbr_vol = df.get("AllTotalVol", pd.Series(0.0, index=df.index)).fillna(0)
        nbr_nb  = df.get("TotalNetBuy", pd.Series(0.0, index=df.index)).fillna(0)
        _use_nbr = net_buy_available and (nbr_vol > 0).any()

        ret_5d_sign = pd.Series(
            np.sign(eq.pct_change(5).values), index=eq.index
        ).fillna(1.0).replace(0.0, 1.0)

        if _use_nbr:
            # ── NBR 籌碼大腦 Barra ─────────────────────────────────────────
            nbr_5d = (
                nbr_nb.rolling(5, min_periods=3).sum()
                / nbr_vol.rolling(5, min_periods=3).sum().replace(0, np.nan)
            ).clip(-1.0, 1.0).fillna(0.0)

            mu_20_nbr    = nbr_5d.rolling(20, min_periods=10).mean()
            sigma_20_nbr = nbr_5d.rolling(20, min_periods=10).std().fillna(0.01)
            nbr_shock    = ((nbr_5d - mu_20_nbr) / (sigma_20_nbr + 1e-9)).clip(-3.0, 3.0)

            signed_shock = pd.Series(
                np.where(nbr_shock.values > 0,
                         nbr_shock.values * ret_5d_sign.values,
                         nbr_shock.values),
                index=eq.index,
            )
            barra_raw = (50.0 + signed_shock * 16.66).clip(0.0, 100.0)
            barra     = barra_raw.where(signed_shock >= 0, other=0.0)
        else:
            # ── 保險大腦：退回 Volume Z-Score Barra ────────────────────────
            mu_20_vol    = vol.rolling(20, min_periods=10).mean()
            sigma_20_vol = vol.rolling(20, min_periods=10).std().fillna(0)
            vol_5d_avg   = vol.rolling(5, min_periods=3).mean()
            vol_shock    = ((vol_5d_avg - mu_20_vol) / (sigma_20_vol + 1e-9)).clip(-3.0, 3.0)
            signed_shock = vol_shock * ret_5d_sign
            barra_raw    = (50.0 + signed_shock * 16.66).clip(0.0, 100.0)
            barra        = barra_raw

        pct_20d = _rolling_hist_pct_rank(vpmi, lookback=20)
        hpct_d[ind] = (0.60 * barra + 0.40 * pct_20d).clip(0.0, 100.0)

    print()

    hpct_df  = pd.DataFrame(hpct_d).fillna(50.0)
    vp_df    = pd.DataFrame(vp_d).fillna(50.0)
    ms_df    = pd.DataFrame(ms_d).fillna(50.0)
    vpmi_df  = pd.DataFrame(vpmi_d).fillna(0.0)
    dev50_df = pd.DataFrame(dev50_d).fillna(0.0)

    alpha_raw = (0.80 * hpct_df + 0.05 * vp_df + 0.15 * ms_df)
    vp_over90  = (vp_df    - 90.0).clip(0.0, 10.0) / 10.0
    dev_over15 = (dev50_df - 15.0).clip(0.0, 15.0) / 15.0
    ob_decay   = (1.0 - 0.30 * vp_over90 * dev_over15).clip(0.70, 1.0)
    alpha_df   = (alpha_raw * ob_decay).clip(0.0, 100.0)

    alpha_pct = alpha_df.rank(axis=1, pct=True, na_option="bottom")
    entry_df  = (alpha_pct >= ENTRY_PCT) & (vp_df >= 40.0)
    pullback_df = (
        (alpha_pct >= 0.45) & (alpha_pct < 0.85)
        & (vp_df >= 55.0) & (vp_df < 85.0)
    )
    exit_df = (vpmi_df < 0.0) & (alpha_pct <= 0.30)

    return alpha_df, entry_df, pullback_df, exit_df


# ─────────────────────────────────────────────────────────────────────────
# 回測引擎（風控邏輯 100% 不變）
# ─────────────────────────────────────────────────────────────────────────
def run_backtest(
    entry_df:          pd.DataFrame,
    pullback_df:       pd.DataFrame,
    exit_df:           pd.DataFrame,
    alpha_df:          pd.DataFrame,
    ind_stock_map:     dict[str, list[str]],
    stock_ret_df:      pd.DataFrame,
    stock_vpmi_df:     pd.DataFrame,
    stock_open_ret_df: pd.DataFrame,
    stock_close_df:    pd.DataFrame,
    spy_close:         pd.Series,
    bt_start_ts:       pd.Timestamp,
    vix_series:        pd.Series,
    breadth_series:    pd.Series,
) -> tuple[pd.Series, list[dict], dict[str, dict], list[pd.Timestamp]]:
    mask     = entry_df.index >= bt_start_ts
    e_df     = entry_df.loc[mask]
    p_df     = pullback_df.loc[mask]
    a_df     = alpha_df.loc[mask]
    bt_dates = list(e_df.index)

    if not bt_dates:
        return pd.Series(dtype=float), [], {}, []

    s_ret      = stock_ret_df.reindex(e_df.index).fillna(0.0)
    s_vpmi     = stock_vpmi_df.reindex(e_df.index).fillna(0.0)
    s_open_ret = stock_open_ret_df.reindex(e_df.index).fillna(0.0)
    s_close    = stock_close_df.reindex(e_df.index).ffill()
    s_ma5      = s_close.rolling(5, min_periods=1).mean()
    s_below5ma = (s_close < s_ma5)

    x_df  = exit_df.reindex(e_df.index).fillna(False)
    pb_df = p_df.reindex(e_df.index).fillna(False)

    vix_r     = vix_series.reindex(e_df.index).ffill().fillna(20.0)
    breadth_r = breadth_series.reindex(e_df.index).ffill().fillna(50.0)
    breadth_3ma  = breadth_r.rolling(3, min_periods=1).mean()
    taper_signal = breadth_3ma.diff().fillna(0.0)

    inds   = list(e_df.columns)
    n_inds = len(inds)

    positions: dict[str, dict] = {}
    cash    = INIT_CAPITAL
    equity: list[float] = []
    trades: list[dict]  = []

    for ti, t in enumerate(bt_dates):

        if ti > 0:
            prev_t = bt_dates[ti - 1]

            _breadth_prev = float(breadth_r.loc[prev_t])
            _vix_prev     = float(vix_r.loc[prev_t])

            if _vix_prev < 22.0:
                dyn_max      = 10
                breakout_cap = 10
            elif _vix_prev < 25.0:
                dyn_max      = int(np.clip(np.floor(5 + _breadth_prev / 15), 1, 9))
                breakout_cap = dyn_max
            else:
                dyn_max      = 1
                breakout_cap = 0

            if prev_t in e_df.index:
                _n_breakout = int(e_df.loc[prev_t].sum())
                if _n_breakout > CLUSTER_WARNING_N:
                    dyn_max      = max(dyn_max - 2, 1)
                    breakout_cap = min(breakout_cap, dyn_max)

            for ticker in list(positions.keys()):
                pos = positions[ticker]
                if pos["exit_flag"]:
                    r = (float(s_open_ret.loc[t, ticker])
                         if ticker in s_open_ret.columns else 0.0)
                    pos["cum_ret"] *= (1.0 + r)
                    trade_ret = pos["cum_ret"] - 1.0
                    proceeds  = pos["alloc"] * pos["cum_ret"]
                    cash     += proceeds
                    trades.append({
                        "標的":     ticker,
                        "産業":     pos["ind"],
                        "入場日":   pos["entry_dt"].strftime("%m/%d"),
                        "出場日":   t.strftime("%m/%d"),
                        "報酬率":   trade_ret,
                        "出場原因": pos["exit_reason"],
                        "勝負":     "✓" if trade_ret > 0 else "✗",
                    })
                    del positions[ticker]

            _tp_prev = float(taper_signal.loc[prev_t]) if prev_t in taper_signal.index else 0.0
            if _tp_prev <= -30.0 and positions:
                for ticker in list(positions.keys()):
                    pos = positions[ticker]
                    open_r = (float(s_open_ret.loc[t, ticker])
                              if ticker in s_open_ret.columns else 0.0)
                    half_cum = pos["cum_ret"] * (1.0 + open_r)
                    cash += pos["alloc"] * 0.5 * half_cum
                    pos["alloc"]  *= 0.5
                    pos["cum_ret"] = 1.0
                    trades.append({
                        "標的":     ticker,
                        "産業":     pos["ind"],
                        "入場日":   pos["entry_dt"].strftime("%m/%d"),
                        "出場日":   t.strftime("%m/%d"),
                        "報酬率":   half_cum - 1.0,
                        "出場原因": "[Global Taper 減碼50%]",
                        "勝負":     "✓" if half_cum >= 1.0 else "✗",
                    })

            open_mktval = sum(pos["alloc"] * pos["cum_ret"] for pos in positions.values())
            current_nav = cash + open_mktval
            slot_size   = current_nav / MAX_POSITIONS

            pos_alpha_map: dict[str, float] = {
                tk: (float(a_df.loc[prev_t, pos["ind"]])
                     if pos["ind"] in a_df.columns else 0.0)
                for tk, pos in positions.items()
            }
            n_breakout_held: int = sum(
                1 for pos in positions.values() if pos.get("sig_type") == "breakout"
            )

            triggered: list[tuple[str, float]] = sorted(
                [(ind, float(a_df.loc[prev_t, ind]))
                 for ind in inds
                 if e_df.loc[prev_t, ind] or pb_df.loc[prev_t, ind]],
                key=lambda x: -x[1],
            )

            for ind, ind_alpha in triggered:
                is_breakout = bool(e_df.loc[prev_t, ind])
                required_gap = (6.0 + n_inds / 5.0) if is_breakout else (12.0 + n_inds / 5.0)

                if is_breakout and n_breakout_held >= breakout_cap:
                    continue

                open_slots = dyn_max - len(positions)

                if open_slots <= 0:
                    lockable = {
                        tk: a for tk, a in pos_alpha_map.items()
                        if positions[tk].get("bars_held", 0) >= MIN_HOLD_BARS
                    }
                    if not lockable:
                        continue
                    weakest_tk    = min(lockable, key=lockable.get)
                    weakest_alpha = lockable[weakest_tk]
                    if ind_alpha < weakest_alpha + required_gap:
                        continue

                    wpos   = positions[weakest_tk]
                    open_r = (float(s_open_ret.loc[t, weakest_tk])
                              if weakest_tk in s_open_ret.columns else 0.0)
                    wpos["cum_ret"] *= (1.0 + open_r)
                    cash            += wpos["alloc"] * wpos["cum_ret"]
                    if wpos.get("sig_type") == "breakout":
                        n_breakout_held = max(n_breakout_held - 1, 0)
                    trades.append({
                        "標的":     weakest_tk,
                        "産業":     wpos["ind"],
                        "入場日":   wpos["entry_dt"].strftime("%m/%d"),
                        "出場日":   t.strftime("%m/%d"),
                        "報酬率":   wpos["cum_ret"] - 1.0,
                        "出場原因": "被排擠出場",
                        "勝負":     "✓" if wpos["cum_ret"] > 1.0 else "✗",
                    })
                    del positions[weakest_tk]
                    del pos_alpha_map[weakest_tk]
                    open_mktval = sum(p["alloc"] * p["cum_ret"] for p in positions.values())
                    slot_size   = (cash + open_mktval) / MAX_POSITIONS
                    open_slots  = 1

                candidates = [
                    sym for sym in ind_stock_map.get(ind, [])
                    if sym not in positions and sym in s_vpmi.columns
                ]
                if not candidates:
                    continue

                vpmi_scores = s_vpmi.loc[prev_t, candidates]
                top_picks   = vpmi_scores[vpmi_scores > 0].nlargest(
                    min(STOCKS_PER_SIGNAL, open_slots)
                )
                if top_picks.empty:
                    continue

                for ticker in top_picks.index:
                    if dyn_max - len(positions) <= 0:
                        break
                    actual_alloc = min(slot_size, cash)
                    if actual_alloc < 1.0:
                        break
                    cash -= actual_alloc
                    positions[ticker] = {
                        "ind":         ind,
                        "alloc":       actual_alloc,
                        "cum_ret":     1.0,
                        "peak_cum":    1.0,
                        "bars_held":   0,
                        "entry_dt":    t,
                        "exit_flag":   False,
                        "exit_reason": "",
                        "sig_type":    "breakout" if is_breakout else "pullback",
                    }
                    if is_breakout:
                        n_breakout_held += 1

        pos_value = 0.0
        for ticker, pos in positions.items():
            r = (float(s_ret.loc[t, ticker]) if ticker in s_ret.columns else 0.0)
            pos["cum_ret"]  *= (1.0 + r)
            pos["bars_held"] = pos.get("bars_held", 0) + 1
            pos["peak_cum"]  = max(pos.get("peak_cum", 1.0), pos["cum_ret"])
            pos_value       += pos["alloc"] * pos["cum_ret"]

            if pos["exit_flag"]:
                continue

            stop_hit         = pos["cum_ret"] <= (1.0 - STOP_LOSS_PCT)
            _trailing_active = pos["peak_cum"] >= (1.0 + TRAILING_TRIGGER_PCT)
            trailing_hit     = _trailing_active and (
                pos["cum_ret"] < pos["peak_cum"] * (1.0 - TRAILING_STOP_PCT)
            )
            ind_exit = (bool(x_df.loc[t, pos["ind"]]) if pos["ind"] in x_df.columns else False)

            b5_today = (bool(s_below5ma.loc[t, ticker]) if ticker in s_below5ma.columns else False)
            b5_prev  = (bool(s_below5ma.loc[bt_dates[bt_dates.index(t) - 1], ticker])
                        if bt_dates.index(t) > 0 and ticker in s_below5ma.columns else False)
            consec_below5 = b5_today and b5_prev

            if stop_hit:
                pos["exit_flag"] = True; pos["exit_reason"] = "停損 -8%"
            elif trailing_hit:
                pos["exit_flag"] = True; pos["exit_reason"] = f"追蹤止盈({TRAILING_STOP_PCT:.0%})"
            elif ind_exit:
                pos["exit_flag"] = True; pos["exit_reason"] = "產業退潮"
            elif consec_below5:
                pos["exit_flag"] = True; pos["exit_reason"] = "連2日跌破5MA"

        equity.append(cash + pos_value)

    for ticker, pos in positions.items():
        trades.append({
            "標的":     ticker,
            "産業":     pos["ind"],
            "入場日":   pos["entry_dt"].strftime("%m/%d"),
            "出場日":   bt_dates[-1].strftime("%m/%d") if bt_dates else "N/A",
            "報酬率":   pos["cum_ret"] - 1.0,
            "出場原因": "回測結束",
            "勝負":     "✓" if pos["cum_ret"] > 1.0 else "✗",
        })

    return (
        pd.Series(equity, index=pd.DatetimeIndex(bt_dates), name="Equity"),
        trades,
        positions,   # 最終未平倉部位
        bt_dates,    # 完整回測日期序列
    )


# ─────────────────────────────────────────────────────────────────────────
# 最新持倉快照
# ─────────────────────────────────────────────────────────────────────────
def build_position_snapshot(
    open_positions: dict[str, dict],
    trades:         list[dict],
    bt_dates:       list[pd.Timestamp],
    equity:         pd.Series | None = None,
) -> dict:
    """
    將回測最終持倉整理成可序列化 dict：
      new / continued / removed + 資金摘要
    """
    if not bt_dates:
        return {
            "as_of": None,
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "n_held": 0,
            "total_mktval": 0.0,
            "new": [],
            "continued": [],
            "removed": [],
            "equity": {},
        }

    last_date = bt_dates[-1]
    last_str  = last_date.strftime("%m/%d")
    last_full = last_date.strftime("%Y-%m-%d")
    total_mktval = sum(p["alloc"] * p["cum_ret"] for p in open_positions.values())

    def _pos_row(ticker: str, pos: dict) -> dict:
        mkt = pos["alloc"] * pos["cum_ret"]
        return {
            "ticker": ticker,
            "industry": pos["ind"],
            "entry_date": pos["entry_dt"].strftime("%Y-%m-%d"),
            "entry_md": pos["entry_dt"].strftime("%m/%d"),
            "alloc_pct": mkt / max(total_mktval, 1.0),
            "pnl": pos["cum_ret"] - 1.0,
            "bars_held": int(pos.get("bars_held", 0)),
            "sig_type": pos.get("sig_type", ""),
        }

    new_entries, continued = [], []
    for ticker, pos in sorted(
        open_positions.items(),
        key=lambda x: (x[1]["entry_dt"], -(x[1]["cum_ret"] - 1.0)),
    ):
        row = _pos_row(ticker, pos)
        if pos["entry_dt"] == last_date:
            new_entries.append(row)
        else:
            continued.append(row)

    removed = [
        {
            "ticker": t["標的"],
            "industry": t["産業"],
            "entry_md": t["入場日"],
            "exit_md": t["出場日"],
            "pnl": float(t["報酬率"]),
            "reason": t.get("出場原因", ""),
        }
        for t in trades
        if t.get("出場日") == last_str and t.get("出場原因") != "回測結束"
    ]
    removed.sort(key=lambda x: x["pnl"])

    equity_info: dict = {}
    if equity is not None and not equity.empty:
        total_ret = float(equity.iloc[-1] / INIT_CAPITAL - 1.0)
        equity_info = {
            "final": float(equity.iloc[-1]),
            "init": float(INIT_CAPITAL),
            "total_ret": total_ret,
            "start": str(equity.index[0].date()),
            "end": str(equity.index[-1].date()),
        }

    return {
        "as_of": last_full,
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_held": len(open_positions),
        "max_positions": MAX_POSITIONS,
        "total_mktval": float(total_mktval),
        "new": new_entries,
        "continued": continued,
        "removed": removed,
        "equity": equity_info,
    }


def save_position_snapshot(snapshot: dict, path: str = PORTFOLIO_JSON) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)
    print(f"  💾 持倉快照已儲存：{path}")


def print_position_summary(
    open_positions: dict[str, dict],
    trades:         list[dict],
    bt_dates:       list[pd.Timestamp],
    init_capital:   float = 100_000.0,
    equity:         pd.Series | None = None,
) -> dict:
    """
    回測結束後列印最新一日持倉狀況，並寫入 data/latest_portfolio.json：
      🆕 本日新增 / 🔄 持續續抱 / ❌ 今日剔除
    """
    SEP  = "═" * 68
    SEP2 = "─" * 68

    snapshot = build_position_snapshot(open_positions, trades, bt_dates, equity=equity)
    save_position_snapshot(snapshot)

    if not bt_dates:
        print(f"\n{SEP}\n  [持倉快照] 無交易日資料。\n{SEP}")
        return snapshot

    last_full = snapshot["as_of"]
    n_held = snapshot["n_held"]
    total_mktval = snapshot["total_mktval"]
    new_entries = snapshot["new"]
    continued = snapshot["continued"]
    removed = snapshot["removed"]

    def _row(r: dict) -> str:
        sig_icon = "🚀" if r.get("sig_type") == "breakout" else "🟢"
        return (
            f"  {r['ticker']:<12} {r['industry']:<22} "
            f"{r['entry_md']:>5}  "
            f"{r['alloc_pct']:>5.1%}  {r['pnl']:>+7.2%}  "
            f"{r['bars_held']:>3}日  {sig_icon}"
        )

    def _removed_row(t: dict) -> str:
        return (
            f"  {t['ticker']:<12} {t['industry']:<22} "
            f"入{t['entry_md']:>5}→出{t['exit_md']:>5}  "
            f"{t['pnl']:>+7.2%}  {t['reason']}"
        )

    col_hdr = (
        f"  {'標的':<12} {'產業':<22} {'入場':>5}  "
        f"{'佔比':>5}  {'損益':>8}  {'持倉':>5}  類型"
    )

    print(f"\n{SEP}")
    print(f"  📊 最新持倉快照  （截至回測最後一日：{last_full}）")
    print(f"  共持有 {n_held} 檔 / 最大 {MAX_POSITIONS} 檔  ·  "
          f"開放部位市值 ${total_mktval:,.0f}")
    print(SEP2)

    print(f"  🆕 本日新增入場（{len(new_entries)} 檔）")
    if new_entries:
        print(col_hdr)
        print(f"  {'─'*12} {'─'*22} {'─'*5}  {'─'*5}  {'─'*8}  {'─'*5}  {'─'*4}")
        for r in new_entries:
            print(_row(r))
    else:
        print("  （無）")
    print(SEP2)

    print(f"  🔄 持續續抱（{len(continued)} 檔）")
    if continued:
        print(col_hdr)
        print(f"  {'─'*12} {'─'*22} {'─'*5}  {'─'*5}  {'─'*8}  {'─'*5}  {'─'*4}")
        for r in continued:
            print(_row(r))
    else:
        print("  （無）")
    print(SEP2)

    print(f"  ❌ 今日剔除出場（{len(removed)} 檔）")
    if removed:
        rmv_hdr = (
            f"  {'標的':<12} {'產業':<22} "
            f"{'入→出場':>13}  {'損益':>8}  出場原因"
        )
        print(rmv_hdr)
        print(f"  {'─'*12} {'─'*22} {'─'*13}  {'─'*8}  {'─'*10}")
        for t in removed:
            print(_removed_row(t))
    else:
        print("  （無）")
    print(SEP + "\n")
    return snapshot


# ─────────────────────────────────────────────────────────────────────────
# 績效報告
# ─────────────────────────────────────────────────────────────────────────
def print_report(
    equity:      pd.Series,
    trades:      list[dict],
    spy_close:   pd.Series,
    bt_start_ts: pd.Timestamp,
) -> None:
    SEP  = "═" * 66
    SEP2 = "─" * 66

    if equity.empty:
        print(f"\n{SEP}\n  [回測結果] 無任何交易信號觸發。\n{SEP}")
        return

    total_ret = equity.iloc[-1] / INIT_CAPITAL - 1.0
    roll_max  = equity.cummax()
    drawdown  = (equity - roll_max) / roll_max
    mdd       = float(drawdown.min())
    daily_ret = equity.pct_change().dropna()
    sharpe    = (float(daily_ret.mean() / daily_ret.std() * np.sqrt(252))
                 if daily_ret.std() > 0 else float("nan"))
    calmar    = (total_ret / abs(mdd)) if mdd < 0 else float("inf")

    rets     = [t["報酬率"] for t in trades]
    n_trades = len(rets)
    winners  = [r for r in rets if r > 0]
    losers   = [r for r in rets if r <= 0]
    win_rate = len(winners) / max(n_trades, 1)
    avg_win  = float(np.mean(winners)) if winners else 0.0
    avg_loss = abs(float(np.mean(losers))) if losers else 1e-9
    pl_ratio = avg_win / avg_loss if avg_loss > 0 else float("inf")
    exp_val  = win_rate * avg_win - (1 - win_rate) * avg_loss

    reason_counts: dict[str, int] = {}
    for t in trades:
        r = t.get("出場原因", "—")
        reason_counts[r] = reason_counts.get(r, 0) + 1

    spy_bt  = spy_close.loc[spy_close.index >= equity.index[0]]
    spy_ret = float(spy_bt.iloc[-1] / spy_bt.iloc[0] - 1) if not spy_bt.empty else float("nan")
    excess  = total_ret - spy_ret

    print(f"\n{SEP}")
    print("  Alpha Score v11.2 NBR 籌碼大腦 雙軌信號策略 — 回測報告")
    print(SEP2)
    print(f"  回測期間        : {equity.index[0].date()} → {equity.index[-1].date()}")
    print(f"  初始資金        : ${INIT_CAPITAL:>12,.0f}")
    print(f"  最終資金        : ${equity.iloc[-1]:>12,.0f}")
    print(f"  最大個股持倉數  : {MAX_POSITIONS}（10等分；動態水位 VIX 閘控）")
    print(f"  停損幅度        : -{STOP_LOSS_PCT:.0%}")
    print(f"  後綴對齊        : .TW 上市 / .TWO 上櫃（已剔除下市殭屍股）")
    print(SEP2)
    print(f"  {'策略總報酬':<16}: {total_ret:>+9.2%}")
    print(f"  {'SOXX 報酬（同期）':<16}: {spy_ret:>+9.2%}")
    print(f"  {'超額報酬 Alpha':<16}: {excess:>+9.2%}")
    print(SEP2)
    print(f"  {'Sharpe Ratio':<16}: {sharpe:>9.2f}")
    print(f"  {'Calmar Ratio':<16}: {calmar:>9.2f}")
    print(f"  {'最大資產回撤 MDD':<16}: {mdd:>9.2%}")

    if not drawdown.empty and drawdown.min() < 0:
        trough_dt = drawdown.idxmin()
        peak_dt   = equity.loc[:trough_dt].idxmax()
        print(f"  {'  回撤區間':<16}: {peak_dt.date()} → {trough_dt.date()}")
    print(SEP2)
    print(f"  {'總交易筆數':<16}: {n_trades:>9d}")
    print(f"  {'勝率':<16}: {win_rate:>9.1%}")
    print(f"  {'賺賠比':<16}: {pl_ratio:>9.2f}x")
    print(f"  {'期望值/每筆':<16}: {exp_val:>+9.2%}")
    print(f"  {'平均獲利':<16}: {avg_win:>+9.2%}")
    print(f"  {'平均虧損':<16}: {-avg_loss:>+9.2%}")
    print(SEP2)
    print("  【出場原因分布】")
    for reason, cnt in sorted(reason_counts.items(), key=lambda x: -x[1]):
        pct = cnt / max(n_trades, 1)
        print(f"    {reason:<14}: {cnt:>3d} 筆 ({pct:.0%})")

    if trades:
        print(f"\n  {'標的':<12} {'産業':<22} {'入場':>5} {'出場':>5}"
              f" {'報酬率':>8} {'出場原因':<10} {'勝負':>3}")
        print(f"  {'─'*12} {'─'*22} {'─'*5} {'─'*5} {'─'*8} {'─'*10} {'─'*3}")
        for t in trades:
            ret_str = f"{t['報酬率']:>+.2%}"
            print(f"  {t['標的']:<12} {t['産業']:<22} {t['入場日']:>5}"
                  f" {t['出場日']:>5} {ret_str:>8} {t['出場原因']:<10} {t['勝負']:>3}")
    print(SEP + "\n")


# ─────────────────────────────────────────────────────────────────────────
# 資金曲線圖
# ─────────────────────────────────────────────────────────────────────────
def plot_equity_chart(
    equity:      pd.Series,
    spy_close:   pd.Series,
    output_path: str = "equity_curve_nbr.png",
) -> None:
    if equity.empty:
        print("  [圖表] equity 為空，跳過繪圖。")
        return

    dates  = equity.index
    init   = INIT_CAPITAL
    bench  = spy_close.reindex(dates, method="ffill").dropna()
    bench_start  = bench.iloc[0] if not bench.empty else 1.0
    bench_equity = bench / bench_start * init

    roll_max  = equity.cummax()
    drawdown  = (equity - roll_max) / roll_max
    trough_i  = int(drawdown.values.argmin())
    peak_i    = int(equity.iloc[:trough_i + 1].values.argmax())
    mdd_start = dates[peak_i]
    mdd_end   = dates[trough_i]
    daily_pnl = equity - init

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(14, 8),
        gridspec_kw={"height_ratios": [3, 1]},
        facecolor="#0f1117",
    )
    fig.subplots_adjust(hspace=0.08)
    for ax in (ax1, ax2):
        ax.set_facecolor("#0f1117")
        ax.tick_params(colors="#cccccc", labelsize=9)
        ax.spines[:].set_color("#333333")
        ax.grid(axis="y", color="#222222", linewidth=0.6)
        ax.grid(axis="x", color="#1c1c1c", linewidth=0.4)

    ax1.axvspan(mdd_start, mdd_end, color="#ff4444", alpha=0.10,
                label=f"MDD 區間 ({drawdown.min():.1%})")
    ax1.axhline(init, color="#555555", linewidth=0.8, linestyle="--", zorder=1)
    ax1.fill_between(dates, init, equity.values,
                     where=(equity.values >= init), alpha=0.12, color="#00c48c", interpolate=True)
    ax1.fill_between(dates, init, equity.values,
                     where=(equity.values < init),  alpha=0.18, color="#ff4444", interpolate=True)

    if not bench_equity.empty:
        bea = bench_equity.reindex(dates, method="ffill")
        ax1.plot(dates, bea.values, color="#f5a623", linewidth=1.2, alpha=0.85,
                 label=f"SOXX 買持  {(bea.iloc[-1]/init - 1):+.1%}")

    final_ret = equity.iloc[-1] / init - 1
    ax1.plot(dates, equity.values, color="#4e9eff", linewidth=1.8,
             label=f"NBR策略  {final_ret:+.1%}")
    ax1.scatter([dates[-1]], [equity.iloc[-1]], color="#4e9eff", s=40, zorder=5)

    ax1_r = ax1.twinx()
    ax1_r.set_ylim((ax1.get_ylim()[0] / init - 1) * 100,
                   (ax1.get_ylim()[1] / init - 1) * 100)
    ax1_r.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:+.0f}%"))
    ax1_r.tick_params(colors="#888888", labelsize=8)
    ax1_r.set_facecolor("#0f1117"); ax1_r.spines[:].set_color("#333333")
    ax1.set_ylabel("資產總值 (USD)", color="#aaaaaa", fontsize=9)
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"${v:,.0f}"))
    ax1.set_title(
        f"Alpha v11.2 NBR 籌碼大腦策略 ─ 資金曲線\n"
        f"初始 ${init:,.0f}  ·  最終 ${equity.iloc[-1]:,.0f}  ·  超額 {(final_ret - (bench_equity.reindex(dates, method='ffill').iloc[-1]/init - 1)):+.1%}",
        color="#ffffff", fontsize=11, pad=10,
    )
    ax1.legend(loc="upper left", fontsize=9, facecolor="#1a1a2e",
               edgecolor="#333333", labelcolor="#cccccc")
    ax1.set_xticklabels([])

    colors_bar = ["#00c48c" if v >= 0 else "#ff4444" for v in daily_pnl.values]
    ax2.bar(dates, daily_pnl.values, color=colors_bar, width=1.0, alpha=0.85)
    ax2.axhline(0, color="#555555", linewidth=0.8, linestyle="--")
    ax2.set_ylabel("盈虧 (USD)", color="#aaaaaa", fontsize=9)
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"${v:+,.0f}"))
    ax2.xaxis.set_major_locator(mdates.MonthLocator())
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=30, ha="right",
             color="#aaaaaa", fontsize=8)

    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="#0f1117")
    plt.close(fig)
    print(f"\n  📈 資金曲線圖已儲存：{output_path}")


# ─────────────────────────────────────────────────────────────────────────
# 主程式
# ─────────────────────────────────────────────────────────────────────────
def main() -> None:
    t_total = time.time()
    SEP = "═" * 66
    print(f"\n{SEP}")
    print("  Alpha v11.2 NBR 籌碼大腦 · 台灣科技產業鏈 — 歷史回測")
    print(f"  回測期間 : {BACKTEST_START} → {BACKTEST_END}")
    print(f"  共 {len(INDUSTRIES)} 個產業 / {len(ALL_TICKERS)} 個標的")
    print(f"  市場過濾 : 台股（.TW 上市 / .TWO 上櫃，已剔除日/韓/美股）")
    print(SEP)

    print(f"\n[0/5] 載入三大法人淨買超歷史資料...")
    net_buy_df = load_net_buy_csv(NET_BUY_CSV)
    if net_buy_df is not None:
        print(f"  ✅ 已載入 {len(net_buy_df)} 交易日 × {net_buy_df.shape[1]} 檔股票法人資料")
        print(f"       ➜ NBR 籌碼大腦：啟動")
    else:
        print(f"  ⚠️  {NET_BUY_CSV} 不存在")
        print(f"       ➜ 缺檔保險大腦：自動退回 Volume Z-Score Barra（防止數值爆炸）")
        print(f"       ➜ 建議先執行 python fetch_net_buy.py 產生資料庫！")

    dl_start = BACKTEST_START - dt.timedelta(days=int(WARMUP_DAYS * 1.5))

    print(f"\n[1/5] 下載日線數據（預熱 {WARMUP_DAYS} 交易日 + 回測期）...")
    panels = download_all(dl_start, BACKTEST_END)
    if len(panels) < 3:
        print("  ERROR: 可用數據不足，請確認網路連線。")
        sys.exit(1)

    spy_close = (
        panels[BENCHMARK]["Close"].dropna()
        if BENCHMARK in panels else pd.Series(dtype=float)
    )

    print(f"\n[2/5] 建構 NBR 產業面板（Top-2 龍頭加權 + 全體 NBR 聚合）...")
    ind_panel = build_industry_panel(panels, net_buy_df=net_buy_df)
    print(f"  有效產業 : {len(ind_panel)} / {len(INDUSTRIES)}")

    print(f"\n[3/5] 建構個股時間序列（台股 .TW/.TWO）...")
    (stock_ret_df, stock_vpmi_df,
     stock_open_ret_df, stock_close_df,
     stock_net_buy_df) = build_stock_frames(panels, net_buy_df=net_buy_df)
    print(f"  可交易個股 : {len(stock_ret_df.columns)} 檔")

    ind_stock_map: dict[str, list[str]] = {
        ind: [t for t in tickers
              if is_tradeable(t) and t in stock_vpmi_df.columns]
        for ind, tickers in INDUSTRIES.items()
    }

    print(f"\n[4/5] 計算産業層級 Alpha v11.2 信號矩陣...")
    t_sig = time.time()
    alpha_df, entry_df, pullback_df, exit_df = build_signal_frames(
        ind_panel, net_buy_available=(net_buy_df is not None)
    )
    print(f"  信號計算耗時 : {time.time() - t_sig:.1f}s")
    print(f"  日期區間     : {entry_df.index[0].date()} → {entry_df.index[-1].date()}")

    if "^VIX" in panels and "Close" in panels["^VIX"].columns:
        vix_close = (panels["^VIX"]["Close"]
                     .reindex(alpha_df.index).ffill().fillna(20.0))
    else:
        vix_close = pd.Series(20.0, index=alpha_df.index, dtype=float)

    _daily_b       = (alpha_df.diff() > 0).sum(axis=1) / alpha_df.shape[1]
    _breadth_5d    = _daily_b.rolling(5, min_periods=1).mean()
    breadth_series = _rolling_hist_pct_rank(_breadth_5d, lookback=20).clip(0.0, 100.0)

    bt_start_ts = pd.Timestamp(BACKTEST_START, tz="UTC")
    bt_mask     = entry_df.index >= bt_start_ts
    n_entry    = int(entry_df.loc[bt_mask].sum().sum())
    n_pullback = int(pullback_df.loc[bt_mask].sum().sum())
    n_exit     = int(exit_df.loc[bt_mask].sum().sum())
    print(f"  🚀 突破進場信號 : {n_entry} 次")
    print(f"  🟢 回踩加碼信號 : {n_pullback} 次")
    print(f"  ❄️  産業退潮信號 : {n_exit} 次")

    print(f"\n[5/5] 執行回測引擎（Alpha v11.2 × VIX 控盤 × 雙軌分路風控）...")
    equity, trades, open_positions, bt_dates = run_backtest(
        entry_df, pullback_df, exit_df, alpha_df,
        ind_stock_map, stock_ret_df, stock_vpmi_df,
        stock_open_ret_df, stock_close_df,
        spy_close, bt_start_ts, vix_close, breadth_series,
    )
    print(f"  完成：{len(trades)} 筆交易")

    print_position_summary(
        open_positions, trades, bt_dates,
        init_capital=INIT_CAPITAL, equity=equity,
    )
    print_report(equity, trades, spy_close, bt_start_ts)
    plot_equity_chart(equity, spy_close, output_path="equity_curve_nbr.png")
    print(f"  Total elapsed : {time.time() - t_total:.1f}s (含下載)")
    print(
        "\n  ✅ 持倉快照已寫入 data/latest_portfolio.json\n"
        "  推播 LINE：python line_alert.py\n"
        "  （排程建議：先跑 backtest_2.py，再跑 line_alert.py）\n"
    )


if __name__ == "__main__":
    main()
