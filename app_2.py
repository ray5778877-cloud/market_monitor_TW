"""台灣科技產業鏈監控 — Alpha v11.2 NBR 籌碼大腦戰情室
資料清洗修正（Millennium 級審計）：
  ① INDUSTRIES 字典對齊 .TW / .TWO 正確後綴，剔除下市殭屍股
  ② fx_rate() / _tw_code() 支援 .TWO 上櫃後綴
  ③ align_panels / build_net_buy_aligned 中的 _is_tw 判斷一律改用 _is_tw_sym()
"""

from __future__ import annotations

import datetime as dt
import json
import os
import time

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
import yfinance as yf

# ---------------------------------------------------------------------------
# 產業配置（上市 .TW / 上櫃 .TWO 後綴精確對齊，已剔除下市殭屍股）
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# 常數
# ---------------------------------------------------------------------------
BENCHMARK = "SOXX"
USD_TWD   = 32.0
USD_JPY   = 155.0
USD_KRW   = 1350.0

UPSTREAM_INDUSTRIES       = ("晶圓廠設備", "前段製程設備")
DOWNSTREAM_INDUSTRIES     = ("晶圓代工", "AI 伺服器組裝")
UPSTREAM_VPMI_THRESHOLD   = 150.0
DOWNSTREAM_VPMI_THRESHOLD =  80.0

LOOKBACK_MONTHS     = 4
MA_SHORT            = 20
MA_LONG             = 50
MOMENTUM_WINDOW     = 5
MOMENTUM_CHART_DAYS = 22
RS_WINDOW           = 20
FVG_LOOKBACK_BARS   = 30
FVG_MAX_DISPLAY     = 6

ALPHA_DELTA_SIGNAL  = 10.0
DOWNLOAD_BATCH_SIZE = 7
DOWNLOAD_RETRY_DELAY = 0.5

TIMEFRAME_OPTIONS = {
    "日線 (1D)":   {"period": "4mo", "interval": "1d"},
    "小時線 (1h)": {"period": "1mo", "interval": "1h"},
}

ALL_TICKERS: tuple[str, ...] = tuple(
    sorted({BENCHMARK, "^VIX"} | {t for tks in INDUSTRIES.values() for t in tks})
)

PLOTLY_CHART_CONFIG = {
    "scrollZoom": True,
    "displayModeBar": True,
    "modeBarButtonsToAdd": ["drawline", "drawopenpath", "eraseshape"],
}

SNIPER_TOP_N = 5
SMC_OB_MULT  = 2.0
SMC_OB_N     = 5
SMC_SWING_N  = 5
SMC_OB_MAX   = 5
SMC_BOS_MAX  = 8
TOP_STOCKS_N = 3
NET_BUY_CSV  = "data/net_buy_shares.csv"
HOLDINGS_JSON = "data/holdings.json"

NAV_OPTIONS = ("今日戰情", "持倉診斷", "產業掃描", "個股研究")


# ---------------------------------------------------------------------------
# 工具函式（全面支援 .TW / .TWO 雙後綴）
# ---------------------------------------------------------------------------
def _is_tw_sym(sym: str) -> bool:
    """True 若為台灣市場標的（上市 .TW 或上櫃 .TWO）。"""
    return sym.endswith(".TW") or sym.endswith(".TWO")


def fx_rate(symbol: str) -> float:
    if symbol.endswith(".TW") or symbol.endswith(".TWO"): return USD_TWD
    if symbol.endswith(".T"):  return USD_JPY
    if symbol.endswith(".KS"): return USD_KRW
    return 1.0


def _tw_code(sym: str) -> str:
    """相容上市(.TW)與上櫃(.TWO)後綴，切出純數字代碼。
    Bug fix：舊 sym[:-3] 對 .TWO 會切出帶小數點的錯誤代碼，已修正。
    """
    if sym.endswith(".TW"):  return sym[:-3]    # "2330.TW"  → "2330"
    if sym.endswith(".TWO"): return sym[:-4]    # "3105.TWO" → "3105"
    return sym


def load_saved_holdings() -> list[str]:
    """從本機 JSON 讀取上次儲存的持股清單。"""
    if not os.path.exists(HOLDINGS_JSON):
        return []
    try:
        with open(HOLDINGS_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return [str(x) for x in data if isinstance(x, str)]
        if isinstance(data, dict) and isinstance(data.get("tickers"), list):
            return [str(x) for x in data["tickers"] if isinstance(x, str)]
    except Exception:
        pass
    return []


def save_holdings(tickers: list[str]) -> None:
    """將持股清單寫入本機 JSON（跨重整持久化）。"""
    try:
        os.makedirs(os.path.dirname(HOLDINGS_JSON) or ".", exist_ok=True)
        with open(HOLDINGS_JSON, "w", encoding="utf-8") as f:
            json.dump(
                {"tickers": list(tickers), "updated_at": dt.datetime.now().isoformat(timespec="seconds")},
                f, ensure_ascii=False, indent=2,
            )
    except Exception:
        pass


def init_holdings_state(tradeable: list[str]) -> None:
    """初始化持股 widget state：優先既有 multiselect，其次本機 JSON。"""
    if "holdings_multiselect" not in st.session_state:
        saved = [t for t in load_saved_holdings() if t in tradeable]
        st.session_state.holdings_multiselect = saved
    else:
        st.session_state.holdings_multiselect = [
            t for t in st.session_state.holdings_multiselect if t in tradeable
        ]
    st.session_state.holdings = list(st.session_state.holdings_multiselect)


def clear_data_caches() -> None:
    """清除行情 / 法人相關 cache，強制下一輪重抓。"""
    try:
        st.cache_data.clear()
    except Exception:
        pass


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


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.rename(columns={c: c.title() for c in df.columns if isinstance(c, str)})
    for col in ("Open", "High", "Low", "Close", "Volume"):
        if col not in out.columns:
            out[col] = np.nan
    return out


def _to_utc_index(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    idx = pd.to_datetime(out.index)
    out.index = idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
    return out.sort_index()


def _extract_ticker_frame(raw: pd.DataFrame, sym: str) -> pd.DataFrame | None:
    if not isinstance(raw.columns, pd.MultiIndex):
        return raw.copy()
    l0, l1 = raw.columns.get_level_values(0), raw.columns.get_level_values(1)
    if sym in l0:
        return raw[sym].copy()
    if sym in l1:
        return raw.xs(sym, axis=1, level=1).copy()
    return None


def _parse_batch(raw: pd.DataFrame, batch: list[str], *, with_volume_usd: bool) -> dict[str, pd.DataFrame]:
    result: dict[str, pd.DataFrame] = {}
    for sym in batch:
        try:
            sub = _extract_ticker_frame(raw, sym)
            if sub is None:
                continue
            sub = _normalize_columns(sub)
            sub = _to_utc_index(sub)
            sub = sub[~sub.index.duplicated(keep="last")]
            sub[["Open", "High", "Low", "Close"]] = sub[["Open", "High", "Low", "Close"]].ffill()
            sub["Volume"] = sub["Volume"].fillna(0)
            if sub["Close"].notna().sum() == 0:
                continue
            if with_volume_usd:
                sub["Volume_USD"] = sub["Close"] * sub["Volume"] / fx_rate(sym)
            result[sym] = sub
        except (KeyError, TypeError, ValueError):
            continue
    return result


def _safe_zscore(series: pd.Series) -> pd.Series:
    valid = series.dropna()
    if len(valid) < 2:
        return pd.Series(0.0, index=series.index)
    mu, sigma = valid.mean(), valid.std(ddof=0)
    if sigma < 1e-9:
        return pd.Series(0.0, index=series.index)
    return ((series - mu) / sigma).clip(-3.0, 3.0)


# ---------------------------------------------------------------------------
# 三大法人資料：歷史載入 + 即時爬取（TWSE 上市 + TPEx 上櫃）
# ---------------------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_twse_institutional(date_str: str) -> dict[str, float]:
    """TWSE RWD T86：上市三大法人。row[18]=三大法人合計買賣超股數。"""
    url = (
        f"https://www.twse.com.tw/rwd/zh/fund/T86"
        f"?response=json&date={date_str}&selectType=ALL"
    )
    try:
        resp = requests.get(url, timeout=12, headers={"User-Agent": "Mozilla/5.0"})
        data = resp.json()
        if data.get("stat") != "OK":
            return {}
        result: dict[str, float] = {}
        for row in data.get("data", []):
            try:
                code = str(row[0]).strip()
                if not code.isdigit():
                    continue
                net = float(str(row[18]).replace(",", ""))
                result[code] = net
            except (ValueError, IndexError):
                pass
        return result
    except Exception:
        return {}


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_tpex_institutional(date_str: str) -> dict[str, float]:
    """TPEx：上櫃三大法人。row[23]=三大法人合計買賣超股數。"""
    try:
        d = dt.datetime.strptime(date_str, "%Y%m%d")
        roc_date = f"{d.year - 1911}/{d.month:02d}/{d.day:02d}"
    except ValueError:
        return {}

    url = (
        "https://www.tpex.org.tw/web/stock/3insti/daily_trade/"
        f"3itrade_hedge_result.php?l=zh-tw&o=json&se=AL&d={roc_date}"
    )
    try:
        resp = requests.get(url, timeout=12, headers={"User-Agent": "Mozilla/5.0"})
        data = resp.json()
        result: dict[str, float] = {}
        for row in data.get("aaData", []):
            try:
                code = str(row[0]).strip()
                if not code.isdigit():
                    continue
                net = float(str(row[23]).replace(",", ""))
                result[code] = net
            except (ValueError, IndexError):
                pass
        return result
    except Exception:
        return {}


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_institutional_data(date_str: str) -> dict[str, float]:
    """合併上市（TWSE）+ 上櫃（TPEx）三大法人買賣超。TWSE 資料優先。"""
    tpex  = fetch_tpex_institutional(date_str)
    twse  = fetch_twse_institutional(date_str)
    return {**tpex, **twse}


@st.cache_data(ttl=1800, show_spinner=False)
def load_net_buy_data() -> pd.DataFrame | None:
    """
    載入歷史三大法人淨買超 CSV，並嘗試以今日即時爬蟲補齊最新一天。
    CSV 格式：index=Date(UTC)，columns=純數字代碼（如 "2330"）
    """
    df: pd.DataFrame = pd.DataFrame()

    if os.path.exists(NET_BUY_CSV):
        try:
            df = pd.read_csv(NET_BUY_CSV, index_col=0, parse_dates=True)
            if df.index.tz is None:
                df.index = df.index.tz_localize("UTC")
            else:
                df.index = df.index.tz_convert("UTC")
            df = df.sort_index()
        except Exception:
            df = pd.DataFrame()

    today_ts  = pd.Timestamp(dt.date.today(), tz="UTC")
    today_str = dt.date.today().strftime("%Y%m%d")

    if df.empty or today_ts not in df.index:
        today_data = fetch_institutional_data(today_str)
        if today_data:
            row_df = pd.DataFrame([today_data], index=[today_ts])
            df = pd.concat([df, row_df]).sort_index() if not df.empty else row_df

    return df if not df.empty else None


def build_net_buy_aligned(
    aligned: dict[str, pd.DataFrame],
    net_buy_df: pd.DataFrame | None,
) -> dict[str, pd.Series]:
    """
    為每個已對齊標的計算「法人淨買超金額（TWD 等值）」時間序列。
    台股（.TW / .TWO）：讀取 net_buy_df[code] × Close / fx_rate
    非台股              ：近似為 Volume × 0.15 × sign(ret_1d)
    """
    result: dict[str, pd.Series] = {}
    for ticker, df in aligned.items():
        if ticker in (BENCHMARK, "^VIX"):
            continue
        close_s  = df["Close"].ffill()
        _is_tw   = _is_tw_sym(ticker)     # ← 支援 .TW / .TWO

        if _is_tw and net_buy_df is not None:
            code = _tw_code(ticker)
            col  = (code       if code   in net_buy_df.columns else
                    ticker     if ticker in net_buy_df.columns else None)
            if col is not None:
                nb_shares = net_buy_df[col].reindex(df.index).ffill().fillna(0)
            else:
                nb_shares = pd.Series(0.0, index=df.index)
        else:
            ret_1d    = close_s.pct_change().fillna(0)
            sign_r    = np.sign(ret_1d).replace(0.0, 1.0)
            nb_shares = df["Volume"].fillna(0) * 0.15 * sign_r

        result[ticker] = (nb_shares * close_s / fx_rate(ticker)).fillna(0)
    return result


# ---------------------------------------------------------------------------
# 數據抓取
# ---------------------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_market_data(tickers: tuple[str, ...]) -> dict[str, pd.DataFrame]:
    end   = dt.date.today()
    start = end - dt.timedelta(days=LOOKBACK_MONTHS * 31 + MA_LONG + 10)
    s_str = start.isoformat()
    e_str = (end + dt.timedelta(days=1)).isoformat()

    ticker_list = list(tickers)
    batches = [ticker_list[i: i + DOWNLOAD_BATCH_SIZE]
               for i in range(0, len(ticker_list), DOWNLOAD_BATCH_SIZE)]
    result: dict[str, pd.DataFrame] = {}

    for batch in batches:
        try:
            raw = yf.download(
                batch, start=s_str, end=e_str,
                interval="1d", group_by="ticker",
                auto_adjust=True, progress=False, threads=True,
            )
            if raw is not None and not raw.empty:
                result.update(_parse_batch(raw, batch, with_volume_usd=True))
        except Exception:
            pass

        missing = [s for s in batch if s not in result]
        for sym in missing:
            try:
                raw_s = yf.download(
                    sym, start=s_str, end=e_str,
                    interval="1d", auto_adjust=True, progress=False,
                )
                if raw_s is not None and not raw_s.empty:
                    result.update(_parse_batch(raw_s, [sym], with_volume_usd=True))
            except Exception:
                pass
        time.sleep(DOWNLOAD_RETRY_DELAY)

    if not result:
        raise ValueError("所有標的均無有效數據。")
    return result


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_chart_data(
    tickers: tuple[str, ...],
    period: str,
    interval: str,
) -> dict[str, pd.DataFrame]:
    ticker_list = list(tickers)
    batches = [ticker_list[i: i + DOWNLOAD_BATCH_SIZE]
               for i in range(0, len(ticker_list), DOWNLOAD_BATCH_SIZE)]
    result: dict[str, pd.DataFrame] = {}
    for batch in batches:
        try:
            raw = yf.download(
                batch, period=period, interval=interval,
                group_by="ticker", auto_adjust=True, progress=False, threads=True,
            )
            if raw is not None and not raw.empty:
                result.update(_parse_batch(raw, batch, with_volume_usd=False))
        except Exception:
            pass
        time.sleep(DOWNLOAD_RETRY_DELAY)
    if not result:
        raise ValueError("K 線數據無法取得。")
    return result


# ---------------------------------------------------------------------------
# 對齊
# ---------------------------------------------------------------------------
def _build_master_calendar(panels: dict[str, pd.DataFrame]) -> pd.DatetimeIndex:
    dates: list = []
    for df in panels.values():
        dates.extend(df.index.tolist())
    return pd.DatetimeIndex(sorted(set(dates)))


def align_panels(panels: dict[str, pd.DataFrame]) -> tuple[pd.DatetimeIndex, dict[str, pd.DataFrame]]:
    calendar = _build_master_calendar(panels)
    aligned: dict[str, pd.DataFrame] = {}
    for sym, df in panels.items():
        out = df.reindex(calendar)
        out[["Open", "High", "Low", "Close"]] = out[["Open", "High", "Low", "Close"]].ffill()
        out["Volume"] = out["Volume"].fillna(0)
        out["Volume"] = clamp_taiwan_volume(
            out["Close"], out["Volume"], _is_tw_sym(sym)   # ← 支援 .TW / .TWO
        )
        out["Volume_USD"] = out["Close"] * out["Volume"] / fx_rate(sym)
        aligned[sym] = out
    return calendar, aligned


def align_panels_utc(panels: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    utc      = {sym: _to_utc_index(df) for sym, df in panels.items()}
    calendar = _build_master_calendar(utc)
    aligned: dict[str, pd.DataFrame] = {}
    for sym, df in utc.items():
        out = df.reindex(calendar)
        out[["Open", "High", "Low", "Close"]] = out[["Open", "High", "Low", "Close"]].ffill()
        out["Volume"] = out["Volume"].fillna(0)
        aligned[sym] = out
    return aligned


# ---------------------------------------------------------------------------
# 量化計算
# ---------------------------------------------------------------------------
def _eq_close_series(tickers: list[str], aligned: dict[str, pd.DataFrame]) -> pd.Series:
    available = [t for t in tickers if t in aligned]
    parts = []
    for t in available:
        s = aligned[t]["Close"].ffill().dropna()
        if not s.empty:
            parts.append(aligned[t]["Close"].ffill() / s.iloc[0] * 100)
    if not parts:
        return pd.Series(dtype=float)
    return pd.concat(parts, axis=1).ffill().mean(axis=1)


def _top2_eq_close(ind_metrics: pd.DataFrame) -> pd.Series:
    ret = ind_metrics["EqReturn"].fillna(0)
    return (1 + ret).cumprod() * 100.0


def compute_industry_metrics(
    industry: str,
    tickers: list[str],
    aligned: dict[str, pd.DataFrame],
    net_buy_aligned: dict[str, pd.Series] | None = None,
) -> pd.DataFrame:
    available = [t for t in tickers if t in aligned]
    if not available:
        raise ValueError(f"{industry} 無可用標的。")

    closes  = pd.concat(
        [aligned[t]["Close"].ffill().rename(t) for t in available], axis=1
    )
    volumes = pd.concat(
        [aligned[t]["Volume_USD"].fillna(0).rename(t) for t in available], axis=1
    )

    ind_ret      = closes.pct_change()
    ind_avg_vol  = volumes.rolling(MA_SHORT, min_periods=MA_SHORT).mean().replace(0, np.nan)
    ind_vol_sum5 = volumes.rolling(MOMENTUM_WINDOW, min_periods=MOMENTUM_WINDOW).sum()
    ind_cum_ret5 = (
        (1 + ind_ret)
        .rolling(MOMENTUM_WINDOW, min_periods=MOMENTUM_WINDOW)
        .apply(np.prod, raw=True) - 1
    )
    stock_vpmi5 = (ind_vol_sum5 / (MOMENTUM_WINDOW * ind_avg_vol)) * ind_cum_ret5 * 100

    TOP_N     = min(2, len(available))
    vpmi_rank = stock_vpmi5.rank(axis=1, ascending=False, na_option="bottom")
    top2_mask = vpmi_rank <= TOP_N
    all_nan   = stock_vpmi5.isna().all(axis=1)
    top2_mask.loc[all_nan] = True

    n_sel        = top2_mask.sum(axis=1).clip(lower=1)
    eq_return    = (ind_ret   * top2_mask).sum(axis=1) / n_sel
    total_volume = (volumes   * top2_mask).sum(axis=1)
    avg_vol_20   = total_volume.rolling(MA_SHORT, min_periods=MA_SHORT).mean().replace(0, np.nan)

    vpmi_1d   = (total_volume / avg_vol_20) * eq_return * 100
    vol_sum_5 = total_volume.rolling(MOMENTUM_WINDOW, min_periods=MOMENTUM_WINDOW).sum()
    cum_ret_5 = (
        (1 + eq_return)
        .rolling(MOMENTUM_WINDOW, min_periods=MOMENTUM_WINDOW)
        .apply(np.prod, raw=True) - 1
    )
    vpmi_5d = (vol_sum_5 / (MOMENTUM_WINDOW * avg_vol_20)) * cum_ret_5 * 100

    all_total_vol = volumes.sum(axis=1)

    if net_buy_aligned is not None:
        nb_parts = [
            net_buy_aligned[t].reindex(closes.index).fillna(0).rename(t)
            for t in available if t in net_buy_aligned
        ]
        total_net_buy = (pd.concat(nb_parts, axis=1).sum(axis=1)
                         if nb_parts else pd.Series(0.0, index=closes.index))
    else:
        total_net_buy = pd.Series(0.0, index=closes.index)

    return pd.DataFrame(
        {
            "EqReturn":       eq_return,
            "TotalVolumeUSD": total_volume,
            "AvgVol20":       avg_vol_20,
            "VPMI_1D":        vpmi_1d,
            "VPMI_5D":        vpmi_5d,
            "AllTotalVol":    all_total_vol,
            "TotalNetBuy":    total_net_buy,
        },
        index=closes.index,
    )


def compute_ma50_dev(
    tickers: list[str],
    aligned: dict[str, pd.DataFrame],
    eq_cl: pd.Series | None = None,
) -> float:
    eq = (eq_cl if eq_cl is not None else _eq_close_series(tickers, aligned)).dropna()
    if len(eq) < MA_LONG:
        return np.nan
    ma50 = eq.rolling(MA_LONG, min_periods=MA_LONG).mean().dropna()
    if ma50.empty:
        return np.nan
    last_ma50 = float(ma50.iloc[-1])
    return (float(eq.iloc[-1]) - last_ma50) / last_ma50 * 100 if last_ma50 != 0 else np.nan


def compute_rs_slope(
    tickers: list[str],
    aligned: dict[str, pd.DataFrame],
    n: int = RS_WINDOW,
    eq_cl: pd.Series | None = None,
) -> float:
    if BENCHMARK not in aligned:
        return np.nan
    eq_close  = eq_cl if eq_cl is not None else _eq_close_series(tickers, aligned)
    spy_close = aligned[BENCHMARK]["Close"].ffill().dropna()
    common = eq_close.dropna().index.intersection(spy_close.index)
    if len(common) < n + 2:
        return np.nan
    eq_c  = eq_close.reindex(common).ffill().dropna().iloc[-(n + 1):]
    spy_c = spy_close.reindex(common).iloc[-(n + 1):]
    if len(eq_c) < n + 1 or len(spy_c) < n + 1:
        return np.nan
    ratio = (eq_c / eq_c.iloc[0]) / (spy_c / spy_c.iloc[0])
    ratio_mean = float(ratio.mean())
    if ratio_mean < 1e-9:
        return np.nan
    slope = float(np.polyfit(np.arange(len(ratio)), ratio.values, 1)[0])
    return slope / ratio_mean * 1000.0


# ---------------------------------------------------------------------------
# Alpha Score v11.2 輔助計算
# ---------------------------------------------------------------------------
def _historical_pct_rank(
    vpmi_series: pd.Series,
    lookback: int = 60,
    lag: int = 0,
) -> float:
    s = vpmi_series.dropna()
    n = len(s)
    if n < 3 + lag:
        return 50.0
    target_pos = n - 1 - lag
    target_val = float(s.iloc[target_pos])
    win_start  = max(0, target_pos - lookback + 1)
    window     = s.iloc[win_start: target_pos + 1]
    rank = float((window < target_val).sum()) / max(len(window), 1) * 100.0
    return float(np.clip(rank, 0.0, 100.0))


def _compute_poc(
    eq_close: pd.Series,
    vol_usd:  pd.Series,
    lookback: int = 60,
    n_bins:   int = 20,
) -> float:
    c = eq_close.tail(lookback).dropna()
    v = vol_usd.reindex(c.index).fillna(0)
    if len(c) < 5:
        return float(c.iloc[-1]) if not c.empty else np.nan
    lo, hi = float(c.min()), float(c.max())
    if hi == lo:
        return float(c.iloc[-1])
    edges   = np.linspace(lo, hi, n_bins + 1)
    bin_idx = np.clip(((c.values - lo) / (hi - lo) * n_bins).astype(int), 0, n_bins - 1)
    vol_bins = np.bincount(bin_idx, weights=v.values, minlength=n_bins)
    poc_i   = int(np.argmax(vol_bins))
    return float((edges[poc_i] + edges[poc_i + 1]) / 2.0)


def _bb_width(eq_close: pd.Series, window: int = 20) -> float:
    c = eq_close.tail(window + 5).dropna()
    if len(c) < window:
        return np.nan
    tail = c.tail(window)
    mu   = float(tail.mean())
    return (4.0 * float(tail.std(ddof=1)) / mu) if mu > 1e-9 else np.nan


# ---------------------------------------------------------------------------
# Alpha Score v11.2 — 主計算（NBR 籌碼大腦版）
# ---------------------------------------------------------------------------
def latest_snapshot(
    metrics:   dict[str, pd.DataFrame],
    ma50_devs: dict[str, float],
    rs_scores: dict[str, float],
    aligned:   dict[str, pd.DataFrame],
) -> pd.DataFrame:
    raw: list[dict] = []

    for industry, series in metrics.items():
        valid    = series.dropna(subset=["VPMI_5D", "EqReturn"])
        ma50_dev = ma50_devs.get(industry, np.nan)
        rs       = rs_scores.get(industry, np.nan)

        if valid.empty:
            raw.append({
                "產業": industry,
                "_vpmi_today": np.nan, "_vpmi_yest": np.nan,
                "_vpmi_pct_today": 50.0, "_vpmi_pct_yest": 50.0,
                "_rs": rs, "_dev": ma50_dev,
                "_vp": 50.0, "_ms": 50.0, "_ms_yest": 50.0, "_bbw": np.nan,
                "最近交易日漲跌幅": np.nan, "1日動能": np.nan,
            })
            continue

        vpmi_today = float(valid["VPMI_5D"].iloc[-1])
        vpmi_yest  = float(valid["VPMI_5D"].iloc[-2]) if len(valid) >= 2 else np.nan
        today_ret  = float(valid["EqReturn"].iloc[-1]) * 100
        vpmi_1d    = float(valid["VPMI_1D"].iloc[-1]) if "VPMI_1D" in valid.columns else np.nan

        eq_cl  = _top2_eq_close(valid)

        # ── NBR 籌碼大腦 Barra ─────────────────────────────────────────────
        if ("TotalNetBuy" in valid.columns and "AllTotalVol" in valid.columns
                and (valid["AllTotalVol"].fillna(0) > 0).any()):
            nbr_nb  = valid["TotalNetBuy"].fillna(0)
            nbr_vol = valid["AllTotalVol"].fillna(0)

            nbr_5d = (
                nbr_nb.rolling(5, min_periods=3).sum()
                / nbr_vol.rolling(5, min_periods=3).sum().replace(0, np.nan)
            ).clip(-1.0, 1.0).fillna(0.0)

            mu_20_nbr    = nbr_5d.rolling(20, min_periods=10).mean()
            sigma_20_nbr = nbr_5d.rolling(20, min_periods=10).std().fillna(0.01)
            nbr_shock    = ((nbr_5d - mu_20_nbr) / (sigma_20_nbr + 1e-9)).clip(-3.0, 3.0)

            ret_5d_sign = pd.Series(
                np.sign(eq_cl.pct_change(5).values), index=eq_cl.index
            ).reindex(valid.index).fillna(1.0).replace(0.0, 1.0)

            signed_shock = pd.Series(
                np.where(nbr_shock.values > 0,
                         nbr_shock.values * ret_5d_sign.values,
                         nbr_shock.values),
                index=valid.index,
            )
            barra_s     = (50.0 + signed_shock * 16.66).clip(0.0, 100.0)
            barra_s     = barra_s.where(signed_shock >= 0, other=0.0)
            barra_today = float(barra_s.iloc[-1]) if len(barra_s) >= 1 else 50.0
            barra_yest  = float(barra_s.iloc[-2]) if len(barra_s) >= 2 else 50.0
        else:
            # 保險大腦：退回 Volume Barra
            vol_ts  = valid.get("TotalVolumeUSD", pd.Series(1.0, index=valid.index))
            mu_20    = vol_ts.rolling(20, min_periods=10).mean()
            sigma_20 = vol_ts.rolling(20, min_periods=10).std().fillna(0)
            vol_5d   = vol_ts.rolling(5, min_periods=3).mean()
            vol_shock_s = ((vol_5d - mu_20) / (sigma_20 + 1e-9)).clip(-3.0, 3.0)
            barra_s     = (50.0 + vol_shock_s * 16.66).clip(0.0, 100.0)
            barra_today = float(barra_s.iloc[-1]) if len(barra_s) >= 1 else 50.0
            barra_yest  = float(barra_s.iloc[-2]) if len(barra_s) >= 2 else 50.0

        pct_20d_today = _historical_pct_rank(valid["VPMI_5D"], lookback=20, lag=0)
        pct_20d_yest  = _historical_pct_rank(valid["VPMI_5D"], lookback=20, lag=1)
        vpmi_pct_today = float(np.clip(0.60 * barra_today + 0.40 * pct_20d_today, 0.0, 100.0))
        vpmi_pct_yest  = float(np.clip(0.60 * barra_yest  + 0.40 * pct_20d_yest,  0.0, 100.0))

        eq_clean = eq_cl.dropna()
        cur_px   = float(eq_clean.iloc[-1]) if not eq_clean.empty else np.nan
        if len(eq_clean) >= 60 and not np.isnan(cur_px):
            dc_win  = eq_clean.tail(60)
            dc_high = float(dc_win.max()); dc_low = float(dc_win.min())
            dc_span = max(dc_high - dc_low, 1e-9)
            vp      = float(np.clip((cur_px - dc_low) / dc_span * 100.0, 0.0, 100.0))
        else:
            vp = 50.0

        ma20   = eq_cl.rolling(20, min_periods=20).mean()
        ma50   = eq_cl.rolling(50, min_periods=50).mean()
        spread = (ma20 - ma50) / ma50.replace(0, np.nan)
        ms      = _historical_pct_rank(spread, lookback=60, lag=0)
        ms_yest = _historical_pct_rank(spread, lookback=60, lag=1)
        bbw     = _bb_width(eq_cl)

        raw.append({
            "產業":            industry,
            "_vpmi_today":     vpmi_today,
            "_vpmi_yest":      vpmi_yest,
            "_vpmi_pct_today": vpmi_pct_today,
            "_vpmi_pct_yest":  vpmi_pct_yest,
            "_rs":             rs,
            "_dev":            ma50_dev,
            "_vp":             vp,
            "_ms":             ms,
            "_ms_yest":        ms_yest,
            "_bbw":            bbw,
            "最近交易日漲跌幅": today_ret,
            "1日動能":         vpmi_1d,
        })

    df_raw = pd.DataFrame(raw)
    vpmi_norm      = df_raw["_vpmi_pct_today"]
    vpmi_yest_norm = df_raw["_vpmi_pct_yest"]

    _vp_ex_t    = (df_raw["_vp"]  - 90.0).clip(0.0, 10.0) / 10.0
    _dev_ex_t   = (df_raw["_dev"] - 15.0).clip(0.0, 15.0) / 15.0
    _ob_decay_t = (1.0 - 0.30 * _vp_ex_t * _dev_ex_t).clip(0.70, 1.0)

    _vp_ex_y    = (df_raw["_vp"]  - 90.0).clip(0.0, 10.0) / 10.0
    _dev_ex_y   = (df_raw["_dev"] - 15.0).clip(0.0, 15.0) / 15.0
    _ob_decay_y = (1.0 - 0.30 * _vp_ex_y * _dev_ex_y).clip(0.70, 1.0)

    alpha_today = (
        (0.80 * vpmi_norm + 0.05 * df_raw["_vp"] + 0.15 * df_raw["_ms"])
        * _ob_decay_t
    ).clip(0.0, 100.0)
    alpha_yest = (
        (0.80 * vpmi_yest_norm + 0.05 * df_raw["_vp"] + 0.15 * df_raw["_ms_yest"])
        * _ob_decay_y
    ).clip(0.0, 100.0)
    alpha_delta = alpha_today - alpha_yest

    alpha_pct = alpha_today.rank(pct=True, na_option="bottom")
    bbw_pct   = df_raw["_bbw"].rank(pct=True, na_option="top", ascending=True)

    cond_breakout = (alpha_pct >= 0.85) & (df_raw["_vp"] >= 40.0)
    cond_pullback = (
        (alpha_pct >= 0.45) & (alpha_pct < 0.85)
        & (df_raw["_vp"] >= 55.0) & (df_raw["_vp"] < 85.0)
    )
    cond_squeeze  = (bbw_pct <= 0.20) & (df_raw["_vpmi_today"].fillna(-1) <= 0)
    cond_cold     = (df_raw["_vpmi_today"].fillna(0) < 0) & (alpha_pct <= 0.30)

    signal = pd.Series("—", index=df_raw.index)
    signal = signal.where(~cond_cold,      "❄️ 資金集體退潮")
    signal = signal.where(~cond_squeeze,   "⏳ 籌碼蓄勢打底")
    signal = signal.where(~cond_pullback,  "🟢 資金回踩支撐")
    signal = signal.where(~cond_breakout,  "🚀 資金突破起漲")

    advice = signal.map({
        "🚀 資金突破起漲": "🔥 強力追擊",
        "🟢 資金回踩支撐": "✅ 穩健分批",
    }).fillna("—")

    return pd.DataFrame({
        "產業":            df_raw["產業"],
        "最近交易日漲跌幅": df_raw["最近交易日漲跌幅"],
        "1日動能":        df_raw["1日動能"],
        "5日動能":        df_raw["_vpmi_today"],
        "RS強弱":         df_raw["_rs"],
        "MA50乖離率":     df_raw["_dev"],
        "VP_Score":       df_raw["_vp"],
        "MS_Score":       df_raw["_ms"],
        "AlphaScore":      alpha_today,
        "Alpha_Delta":     alpha_delta,
        "VPMI_v11_Score":  df_raw["_vpmi_pct_today"],
        "戰情燈號":       signal,
        "決策建議":       advice,
    })


def check_arbitrage_alert(snapshot: pd.DataFrame) -> bool:
    by_name = snapshot.set_index("產業")["5日動能"]
    up_hot  = any(by_name.get(ind, np.nan) > UPSTREAM_VPMI_THRESHOLD   for ind in UPSTREAM_INDUSTRIES)
    dn_cold = any(by_name.get(ind, np.nan) < DOWNSTREAM_VPMI_THRESHOLD for ind in DOWNSTREAM_INDUSTRIES)
    return up_hot and dn_cold


def get_stock_momentum_scores(
    tickers: list[str],
    aligned: dict[str, pd.DataFrame],
    top_n: int = TOP_STOCKS_N,
) -> list[tuple[str, float]]:
    scores: list[tuple[str, float]] = []
    for t in tickers:
        if t not in aligned:
            continue
        df = aligned[t]
        closes  = df["Close"].ffill().dropna()
        vol_usd = df.get("Volume_USD", pd.Series(dtype=float)).fillna(0)
        if len(closes) < MA_SHORT + MOMENTUM_WINDOW:
            continue
        ret = closes.pct_change()
        avg_vol = vol_usd.rolling(MA_SHORT, min_periods=MA_SHORT).mean()
        vol_sum = vol_usd.rolling(MOMENTUM_WINDOW, min_periods=MOMENTUM_WINDOW).sum()
        cum_ret = (1 + ret).rolling(MOMENTUM_WINDOW, min_periods=MOMENTUM_WINDOW).apply(
            lambda x: np.prod(x) - 1, raw=True
        )
        vpmi = (vol_sum / (MOMENTUM_WINDOW * avg_vol)) * cum_ret * 100
        last = vpmi.dropna()
        if not last.empty:
            scores.append((t, float(last.iloc[-1])))
    return sorted(scores, key=lambda x: x[1], reverse=True)[:top_n]


def _get_stock_ohlc(
    ticker: str,
    aligned: dict[str, pd.DataFrame],
    max_bars: int = 90,
) -> pd.DataFrame | None:
    if ticker not in aligned:
        return None
    df = aligned[ticker].copy()
    df = df[df["Volume"] > 0]
    df = df[["Open", "High", "Low", "Close"]].dropna(subset=["Close"])
    return df.tail(max_bars) if not df.empty else None


def _stock_vpmi5(close_s: pd.Series, vol_usd_s: pd.Series) -> float:
    avg_vol  = vol_usd_s.rolling(MA_SHORT, min_periods=MA_SHORT).mean().replace(0, np.nan)
    vol_sum5 = vol_usd_s.rolling(MOMENTUM_WINDOW, min_periods=MOMENTUM_WINDOW).sum()
    ret      = close_s.pct_change()
    cum5     = (1 + ret).rolling(MOMENTUM_WINDOW, min_periods=MOMENTUM_WINDOW).apply(
        lambda x: float(np.prod(x)) - 1.0, raw=True
    )
    vpmi_s = (vol_sum5 / (MOMENTUM_WINDOW * avg_vol)) * cum5 * 100.0
    return float(vpmi_s.iloc[-1]) if not vpmi_s.dropna().empty else np.nan


# ---------------------------------------------------------------------------
# UI 元件
# ---------------------------------------------------------------------------
def _position_label(dev: float) -> tuple[str, str]:
    if np.isnan(dev):     return "N/A", "#888888"
    if dev < -5:          return "深度超跌", "#1565C0"
    if dev < 0:           return "輕度超跌", "#1976D2"
    if dev < 5:           return "最佳買點 ✨", "#2E7D32"
    if dev < 15:          return "追漲風險", "#F57F17"
    return "超買警戒", "#C62828"


def _heat_label(vpmi: float) -> str:
    if np.isnan(vpmi):   return "N/A"
    if vpmi > 150:       return "🔴 極熱"
    if vpmi > 80:        return "🟠 偏熱"
    if vpmi > 20:        return "🟡 升溫"
    if vpmi > 0:         return "⚪ 平溫"
    return "🔵 冷卻"


def _rs_label(rs: float) -> str:
    if np.isnan(rs):     return "N/A"
    if rs > 5:           return f"+{rs:.2f} 強勢跑贏"
    if rs > 0:           return f"+{rs:.2f} 小幅跑贏"
    if rs > -5:          return f"{rs:.2f} 小幅落後"
    return f"{rs:.2f} 明顯落後"


def render_position_diagnostics(
    snapshot:   pd.DataFrame,
    aligned:    dict[str, pd.DataFrame],
    gate_slots: int,
) -> dict[str, int]:
    """持倉診斷；回傳 {'force': n, 'warn': n, 'hold': n} 供首屏摘要。"""
    st.subheader("🎯 實戰持倉即時診斷與動態換血雷達")

    tradeable_opts = sorted([
        t for t in ALL_TICKERS
        if t not in (BENCHMARK, "^VIX") and _is_tw_sym(t)
    ])
    init_holdings_state(tradeable_opts)

    c_sel, c_btn = st.columns([5, 1])
    with c_sel:
        selected: list[str] = st.multiselect(
            "📋 請勾選目前帳戶持有的個股（會自動記住）",
            options=tradeable_opts,
            placeholder="輸入 Ticker 搜尋（如 2330.TW、3105.TWO、3711.TW）",
            key="holdings_multiselect",
        )
    with c_btn:
        st.write("")  # 對齊高度
        if st.button("清除持股", use_container_width=True, key="clear_holdings_btn"):
            st.session_state.holdings_multiselect = []
            st.session_state.holdings = []
            save_holdings([])
            st.rerun()

    if selected != st.session_state.get("holdings", []):
        st.session_state.holdings = selected
        save_holdings(selected)

    if not selected:
        st.info("💡 請在上方輸入目前持股，啟動機構級實戰體檢（清單會寫入 `data/holdings.json`）")
        return {"force": 0, "warn": 0, "hold": 0}

    ticker_to_ind: dict[str, str] = {}
    for ind, tks in INDUSTRIES.items():
        for tk in tks:
            if tk not in ticker_to_ind:
                ticker_to_ind[tk] = ind

    snap_by_ind = (snapshot.set_index("產業")
                   if not snapshot.empty and "產業" in snapshot.columns
                   else pd.DataFrame())
    market_top1_alpha = float(snapshot["AlphaScore"].max()) if not snapshot.empty else 0.0
    market_top1_ind   = (str(snapshot.loc[snapshot["AlphaScore"].idxmax(), "產業"])
                         if not snapshot.empty else "—")

    n_held    = len(selected)
    remaining = 10 - n_held
    col_l, col_r = st.columns(2)
    with col_l:
        st.metric("已動用槽位", f"{n_held} / 10",
                  f"尚餘 {remaining} 槽" if remaining > 0 else "滿倉",
                  delta_color="off")
    with col_r:
        st.metric("閘門允許最高槽位", f"{gate_slots} / 10",
                  "Alpha v11.2 VIX 動態水位", delta_color="off")

    n_inds       = len(INDUSTRIES)
    gap_breakout = 6.0  + (n_inds / 5.0)
    gap_fallback = 12.0 + (n_inds / 5.0)
    st.caption(
        f"🏆 今日全市場 Alpha Top 1：**{market_top1_ind}**（α = {market_top1_alpha:.1f}）"
        f"｜排擠門檻 🚀{gap_breakout:.1f} / 🟢{gap_fallback:.1f}（{n_inds} 産業）"
        f"  ·  **.TW 上市 / .TWO 上櫃 雙後綴已對齊**"
    )

    rows: list[dict] = []
    force_exit_stocks: list[str] = []
    warning_stocks:    list[str] = []

    for tk in selected:
        ind = ticker_to_ind.get(tk, "—")
        if ind != "—" and ind in snap_by_ind.index:
            ir         = snap_by_ind.loc[ind]
            ind_alpha  = float(ir.get("AlphaScore",    np.nan))
            ind_delta  = float(ir.get("Alpha_Delta",   np.nan))
            ind_vpmi7  = float(ir.get("VPMI_v11_Score", np.nan))
            ind_signal = str(ir.get("戰情燈號",        "—"))
        else:
            ind_alpha = ind_delta = ind_vpmi7 = np.nan
            ind_signal = "—"

        alpha_gap     = (market_top1_alpha - ind_alpha if not np.isnan(ind_alpha) else np.nan)
        consec_below5 = False
        below5_today  = False
        ma5_dev_pct   = np.nan
        vpmi5d        = np.nan

        if tk in aligned:
            df_tk   = aligned[tk]
            close_s = df_tk["Close"].ffill().dropna()
            if len(close_s) >= 5:
                ma5_s         = close_s.rolling(5, min_periods=1).mean()
                below5_today  = bool(close_s.iloc[-1] < ma5_s.iloc[-1])
                below5_prev   = bool(close_s.iloc[-2] < ma5_s.iloc[-2]) if len(close_s) >= 6 else False
                consec_below5 = below5_today and below5_prev
                ma5_val       = float(ma5_s.iloc[-1])
                ma5_dev_pct   = ((float(close_s.iloc[-1]) - ma5_val) / ma5_val * 100.0
                                 if ma5_val != 0.0 else np.nan)
            if len(close_s) >= MA_SHORT + MOMENTUM_WINDOW:
                vol_usd_s = df_tk.get("Volume_USD", pd.Series(dtype=float)).fillna(0)
                vpmi5d    = _stock_vpmi5(close_s, vol_usd_s)

        is_cold   = "❄️" in ind_signal
        _gap_thresh = gap_breakout if "🚀" in ind_signal else gap_fallback
        force_gap   = not np.isnan(alpha_gap) and alpha_gap >= _gap_thresh

        if consec_below5 or is_cold or force_gap:
            diag   = "🚨 汰弱留強"
            action = (f"❌ 次日開盤市價全額平倉，騰槽換倉至「{market_top1_ind}」龍頭股！")
            force_exit_stocks.append(tk)
        elif (below5_today or
              (not np.isnan(ma5_dev_pct) and abs(ma5_dev_pct) >= 15.0) or
              (not np.isnan(vpmi5d) and vpmi5d <= 0.0)):
            diag   = "⚠️ 減碼警戒"
            action = "⚠️ 動能走弱或過熱，建議減碼 50% 落袋。"
            warning_stocks.append(tk)
        else:
            diag   = "🟢 強勢續抱"
            action = "🔥 籌碼健康，鐵股續抱讓利潤複利奔跑。"

        rows.append({
            "持倉標的":     tk,
            "所屬產業":     ind,
            "產業 Alpha":   round(ind_alpha,  1) if not np.isnan(ind_alpha)  else None,
            "與Top1分差":   round(alpha_gap,  1) if not np.isnan(alpha_gap)  else None,
            "5MA 乖離%":    round(ma5_dev_pct, 1) if not np.isnan(ma5_dev_pct) else None,
            "連2日破5MA":   "🔴 是" if consec_below5 else "🟢 否",
            "診斷狀態":     diag,
            "實戰操作指引": action,
        })

    diag_df = pd.DataFrame(rows)
    _DIAG_COLORS = {
        "🚨": ("background-color:#FFEBEE", "color:#B71C1C; font-weight:700"),
        "⚠️": ("background-color:#FFF3E0", "color:#E65100; font-weight:700"),
        "🟢": ("background-color:#E8F5E9", "color:#1B5E20; font-weight:700"),
    }

    def _style_row(row: pd.Series) -> list[str]:
        diag = str(row.get("診斷狀態", ""))
        for key, (bg, fg) in _DIAG_COLORS.items():
            if key in diag:
                return [f"{bg}; {fg}"] * len(row)
        return [""] * len(row)

    st.dataframe(diag_df.style.apply(_style_row, axis=1), use_container_width=True, hide_index=True)

    if force_exit_stocks:
        st.error(
            f"🚨 **強制平倉警告**：**{'  /  '.join(force_exit_stocks)}** 觸發汰弱留強\n\n"
            f"🎯 換倉目標：**{market_top1_ind}**（α = {market_top1_alpha:.1f}）"
        )
    if warning_stocks:
        st.warning(f"⚠️ **減碼警戒**：**{'  /  '.join(warning_stocks)}** 建議減碼 50%")

    n_hold = max(len(selected) - len(force_exit_stocks) - len(warning_stocks), 0)
    return {
        "force": len(force_exit_stocks),
        "warn":  len(warning_stocks),
        "hold":  n_hold,
    }


def render_sniper_scanner(snapshot: pd.DataFrame) -> None:
    valid_snap = snapshot.dropna(subset=["AlphaScore"])
    top5 = valid_snap.nlargest(SNIPER_TOP_N, "AlphaScore").reset_index(drop=True)

    st.markdown("#### 🔥 今日狙擊清單（Alpha Top 5）")
    if top5.empty:
        st.info("數據不足，無法產生狙擊清單。")
        return
    cols = st.columns(SNIPER_TOP_N)
    for rank, (col, row) in enumerate(zip(cols, top5.iterrows()), start=1):
        _, row = row
        alpha  = row["AlphaScore"]
        delta  = row["Alpha_Delta"]
        dev    = row["MA50乖離率"]
        vpmi5  = row["5日動能"]
        rs_v   = row["RS強弱"]
        advice = row["決策建議"]
        pos_lbl, pos_color = _position_label(dev)
        dev_str   = "N/A" if np.isnan(dev) else f"{dev:+.1f}%"
        delta_str = None if np.isnan(delta) else f"{delta:+.1f}"
        ind_name  = str(row["產業"])

        with col:
            st.metric(
                label=f"#{rank}  {ind_name}",
                value=f"α {alpha:.1f}",
                delta=delta_str,
                delta_color="normal",
            )
            if not np.isnan(delta) and delta > ALPHA_DELTA_SIGNAL:
                st.markdown(
                    "<span style='color:#C62828;font-size:12px;font-weight:700;'>"
                    "🚀 法人加速建倉</span>",
                    unsafe_allow_html=True,
                )
            advice_color = {"✅ 黃金進場": "#2E7D32", "⚠️ 過熱風險": "#E65100"}.get(advice, "#555555")
            st.markdown(
                f"<div style='font-size:13px;font-weight:700;color:{advice_color};margin:-4px 0 6px 0;'>"
                f"{advice}</div>", unsafe_allow_html=True,
            )
            st.markdown(
                f"<div style='font-size:11px;line-height:1.7;color:#444;'>"
                f"💰 資金熱度：{_heat_label(vpmi5)}<br>"
                f"📈 RS強弱：{_rs_label(rs_v)}<br>"
                f"<span style='color:{pos_color};font-weight:600;'>"
                f"📍 {pos_lbl}（{dev_str}）</span></div>",
                unsafe_allow_html=True,
            )
            if st.button("研究此產業 →", key=f"snip_jump_{rank}", use_container_width=True):
                st.session_state["ind_sel"] = ind_name
                st.session_state["nav"] = "個股研究"
                st.rerun()


# ---------------------------------------------------------------------------
# 圖表
# ---------------------------------------------------------------------------
def build_rotation_scatter(snapshot: pd.DataFrame) -> go.Figure:
    df   = snapshot.dropna(subset=["5日動能", "MA50乖離率"]).copy()
    xmax = max(float(df["5日動能"].abs().max()) * 1.4, 40) if not df.empty else 100
    ymax = max(float(df["MA50乖離率"].abs().max()) * 1.4, 8) if not df.empty else 15

    fig = go.Figure()
    for x0, x1, y0, y1, color, label, tx, ty in [
        ( 0,  xmax,  0,  ymax, "rgba(144,238,144,0.12)", "主升段",             xmax*.65,  ymax*.75),
        ( 0,  xmax, -ymax, 0,  "rgba(135,206,235,0.12)", "底倉起漲\n(黃金坑)", xmax*.65, -ymax*.75),
        (-xmax, 0,  0,  ymax,  "rgba(255,215,0,0.10)",   "高檔退潮",           -xmax*.65,  ymax*.75),
        (-xmax, 0, -ymax, 0,   "rgba(255,100,100,0.10)", "冷宮區",             -xmax*.65, -ymax*.75),
    ]:
        fig.add_shape(type="rect", x0=x0, x1=x1, y0=y0, y1=y1,
                      fillcolor=color, line_width=0, layer="below")
        fig.add_annotation(x=tx, y=ty, text=label, showarrow=False,
                           xref="x", yref="y",
                           font=dict(size=13, color="rgba(120,120,120,0.55)"))

    fig.add_vline(x=0, line_dash="dash", line_color="rgba(80,80,80,0.4)", line_width=1)
    fig.add_hline(y=0, line_dash="dash", line_color="rgba(80,80,80,0.4)", line_width=1)
    alpha_vals = df["AlphaScore"].fillna(20).clip(8, 60) if "AlphaScore" in df.columns else pd.Series(16, index=df.index)
    fig.add_trace(go.Scatter(
        x=df["5日動能"], y=df["MA50乖離率"],
        mode="markers+text",
        text=df["產業"], textposition="top center", textfont=dict(size=10),
        marker=dict(
            size=alpha_vals.tolist(),
            color=df["AlphaScore"] if "AlphaScore" in df.columns else df["5日動能"],
            colorscale="RdYlGn", cmin=alpha_vals.min(), cmax=alpha_vals.max(),
            showscale=True,
            colorbar=dict(title="Alpha", thickness=12, len=0.6),
            line=dict(width=1, color="rgba(0,0,0,0.2)"),
        ),
        hovertemplate=(
            "<b>%{text}</b><br>5日動能: %{x:.2f}<br>"
            "MA50乖離率: %{y:.2f}%<extra></extra>"
        ),
    ))
    fig.update_layout(
        title="資金輪動四象限（法人 NBR 5日動能 × MA50乖離率）",
        xaxis_title="← 法人退出　5日動能 (VPMI_5D)　法人進駐 →",
        yaxis_title="← 超跌區　距 50MA 乖離率 (%)　超買區 →",
        height=520, template="plotly_white", showlegend=False,
        margin=dict(t=60, b=60),
    )
    fig.update_xaxes(range=[-xmax, xmax], zeroline=False)
    fig.update_yaxes(range=[-ymax, ymax], zeroline=False)
    return fig


def build_equal_weight_ohlc(
    tickers: list[str],
    aligned: dict[str, pd.DataFrame],
    *,
    filter_empty_bars: bool = False,
) -> pd.DataFrame:
    available = [t for t in tickers if t in aligned]
    if not available:
        raise ValueError("無可用標的。")
    vol_total = pd.concat([aligned[t]["Volume"].rename(t) for t in available], axis=1).sum(axis=1)
    parts = {
        t: (aligned[t][["Open", "High", "Low", "Close"]].ffill()
            / aligned[t]["Close"].ffill().dropna().iloc[0] * 100)
        for t in available
    }
    ohlc = pd.DataFrame(index=parts[available[0]].index)
    for col in ("Open", "High", "Low", "Close"):
        ohlc[col] = pd.concat([parts[t][col] for t in available], axis=1).mean(axis=1)
    ohlc = ohlc.dropna(subset=["Close"])
    if filter_empty_bars:
        ohlc = ohlc.loc[vol_total.reindex(ohlc.index).fillna(0) > 0]
    return ohlc


def _detect_bullish_fvg(chart: pd.DataFrame) -> list[tuple[float, float]]:
    recent = chart.tail(FVG_LOOKBACK_BARS).reset_index(drop=True)
    fvgs: list[tuple[float, float]] = []
    for i in range(len(recent) - 2):
        h0 = float(recent["High"].iloc[i])
        l2 = float(recent["Low"].iloc[i + 2])
        if l2 > h0:
            fvgs.append((h0, l2))
    return fvgs[::-1][:FVG_MAX_DISPLAY]


def _detect_order_blocks_smc(ohlc, mult=SMC_OB_MULT, n_avg=SMC_OB_N, max_obs=SMC_OB_MAX):
    highs  = ohlc["High"].values; lows   = ohlc["Low"].values
    closes = ohlc["Close"].values; opens  = ohlc["Open"].values
    ranges = highs - lows; idx = ohlc.index
    obs: list[dict] = []
    for i in range(n_avg + 1, len(ohlc) - 1):
        avg_rng = ranges[i - n_avg: i].mean()
        if avg_rng < 1e-9 or ranges[i] < mult * avg_rng:
            continue
        ob_i = i - 1
        ob_high = float(highs[ob_i]); ob_low = float(lows[ob_i])
        ob_date = idx[ob_i]
        is_bull = float(closes[i]) > float(opens[i])
        fut_lows = lows[i + 1:]; fut_highs = highs[i + 1:]
        mitigated = (bool(np.any(fut_lows <= ob_high)) if is_bull
                     else bool(np.any(fut_highs >= ob_low)))
        if not mitigated:
            obs.append({"date": ob_date, "impulse": idx[i],
                        "high": ob_high, "low": ob_low, "bullish": is_bull})
    return obs[-max_obs:]


def _detect_bos_smc(ohlc, swing_n=SMC_SWING_N, max_bos=SMC_BOS_MAX):
    highs = ohlc["High"].values; lows = ohlc["Low"].values
    closes = ohlc["Close"].values; idx = ohlc.index; n = len(ohlc)

    def _sh(i):
        return (i >= swing_n and i + swing_n < n
                and all(highs[i] >= highs[i - k] for k in range(1, swing_n + 1))
                and all(highs[i] >= highs[i + k] for k in range(1, swing_n + 1)))

    def _sl(i):
        return (i >= swing_n and i + swing_n < n
                and all(lows[i] <= lows[i - k] for k in range(1, swing_n + 1))
                and all(lows[i] <= lows[i + k] for k in range(1, swing_n + 1)))

    bos: list[dict] = []
    for i in range(swing_n, n - swing_n - 1):
        if _sh(i):
            for j in range(i + swing_n, min(i + 40, n)):
                if closes[j] > highs[i]:
                    bos.append({"date": idx[j], "level": float(highs[i]),
                                "bullish": True, "swing_dt": idx[i]}); break
        if _sl(i):
            for j in range(i + swing_n, min(i + 40, n)):
                if closes[j] < lows[i]:
                    bos.append({"date": idx[j], "level": float(lows[i]),
                                "bullish": False, "swing_dt": idx[i]}); break
    return sorted(bos, key=lambda x: x["date"])[-max_bos:]


def _detect_entry_signals_smc(ohlc, obs, bos_events, fvgs):
    entries: list[dict] = []
    bull_bos = [b for b in bos_events if b["bullish"]]
    if not bull_bos:
        return entries
    last_bull_bos_dt = bull_bos[-1]["date"]
    if last_bull_bos_dt not in ohlc.index:
        return entries
    bos_pos = ohlc.index.get_loc(last_bull_bos_dt)
    future  = ohlc.iloc[bos_pos + 1:]
    seen_dt: set = set()
    for ob in obs:
        if not ob["bullish"] or ob["date"] >= last_bull_bos_dt:
            continue
        for dt_idx, row in future.iterrows():
            if row["Low"] <= ob["high"] and row["High"] >= ob["low"] and dt_idx not in seen_dt:
                entries.append({"date": dt_idx, "price": float(row["Low"]), "zone": "OB"})
                seen_dt.add(dt_idx); break
    for fvg_low, fvg_high in fvgs:
        for dt_idx, row in future.iterrows():
            if row["Low"] <= fvg_high and row["High"] >= fvg_low and dt_idx not in seen_dt:
                entries.append({"date": dt_idx, "price": float(row["Low"]), "zone": "FVG"})
                seen_dt.add(dt_idx); break
    return sorted(entries, key=lambda x: x["date"])


def build_smc_chart(ohlc: pd.DataFrame, title: str, interval: str) -> go.Figure:
    chart = ohlc.copy()
    chart["MA20"] = chart["Close"].rolling(MA_SHORT, min_periods=1).mean()
    chart["MA50"] = chart["Close"].rolling(MA_LONG,  min_periods=1).mean()
    fvgs       = _detect_bullish_fvg(chart)
    obs        = _detect_order_blocks_smc(chart)
    bos_events = _detect_bos_smc(chart)
    entries    = _detect_entry_signals_smc(chart, obs, bos_events, fvgs)
    fig  = go.Figure()
    last_dt = chart.index[-1]
    for fi, (y0, y1) in enumerate(fvgs):
        fig.add_hrect(y0=y0, y1=y1, fillcolor="rgba(255,230,100,0.18)", line_width=0,
                      annotation_text="FVG" if fi == 0 else "",
                      annotation_position="right",
                      annotation=dict(font=dict(size=9, color="#8B6914")))
    for ob in obs:
        fill = "rgba(147,112,219,0.18)" if ob["bullish"] else "rgba(220,80,80,0.15)"
        line = "rgba(120,60,200,0.6)"   if ob["bullish"] else "rgba(200,50,50,0.6)"
        fig.add_shape(type="rect", x0=ob["date"], x1=last_dt, y0=ob["low"], y1=ob["high"],
                      xref="x", yref="y", fillcolor=fill,
                      line=dict(color=line, width=1, dash="dot"), layer="below")
        fig.add_annotation(x=ob["date"], y=ob["high"],
                           text="↑OB" if ob["bullish"] else "↓OB", showarrow=False,
                           xanchor="left", yanchor="bottom",
                           font=dict(size=9, color="#6A0DAD" if ob["bullish"] else "#C62828",
                                     family="monospace"))
    fig.add_trace(go.Candlestick(
        x=chart.index, open=chart["Open"], high=chart["High"],
        low=chart["Low"], close=chart["Close"], name="K 線",
        increasing_line_color="#26A69A", decreasing_line_color="#EF5350",
    ))
    fig.add_trace(go.Scatter(x=chart.index, y=chart["MA20"], mode="lines", name="MA20",
                             line=dict(color="#FB8C00", width=1.2)))
    fig.add_trace(go.Scatter(x=chart.index, y=chart["MA50"], mode="lines", name="MA50",
                             line=dict(color="#1E88E5", width=1.2)))
    for bos in bos_events:
        if bos["date"] not in chart.index:
            continue
        bar   = chart.loc[bos["date"]]
        is_up = bos["bullish"]
        color = "#1565C0" if is_up else "#B71C1C"
        y_ann = float(bar["Low"]) * 0.997 if is_up else float(bar["High"]) * 1.003
        fig.add_annotation(x=bos["date"], y=y_ann,
                           text="<b>BOS↑</b>" if is_up else "<b>BOS↓</b>",
                           showarrow=True, arrowhead=2, arrowsize=1.2, arrowcolor=color,
                           font=dict(size=9, color=color), ax=0, ay=25 if is_up else -25,
                           bgcolor="rgba(255,255,255,0.75)",
                           bordercolor=color, borderwidth=1, borderpad=2)
        fig.add_shape(type="line", x0=bos["swing_dt"], x1=bos["date"],
                      y0=bos["level"], y1=bos["level"], xref="x", yref="y",
                      line=dict(color=color, width=1, dash="dash"))
    e_dates  = [e["date"]  for e in entries if e["date"] in chart.index]
    e_prices = [e["price"] * 0.997 for e in entries if e["date"] in chart.index]
    e_zones  = [e["zone"]  for e in entries if e["date"] in chart.index]
    if e_dates:
        fig.add_trace(go.Scatter(
            x=e_dates, y=e_prices, mode="markers+text",
            marker=dict(symbol="triangle-up", size=14, color="rgba(0,180,60,0.9)",
                        line=dict(color="#004d1a", width=1)),
            text=[f"Entry ({z})" for z in e_zones], textposition="bottom center",
            textfont=dict(size=9, color="#004d1a"), name="Entry 訊號",
        ))
    fig.update_layout(
        title=title, yaxis_title="價格",
        height=600, template="plotly_white",
        hovermode="x unified", dragmode="zoom", uirevision=title,
        legend=dict(orientation="h", yanchor="bottom", y=1.08, xanchor="right", x=1),
        margin=dict(t=80, b=60),
    )
    brks = [dict(bounds=["sat", "mon"])]
    if interval == "1h":
        brks.append(dict(bounds=[17, 9.5], pattern="hour"))
    btns = ([dict(count=5, label="5D", step="day", stepmode="backward"),
             dict(count=1, label="1M", step="month", stepmode="backward"),
             dict(step="all", label="All")] if interval == "1h" else
            [dict(count=5, label="5D", step="day", stepmode="backward"),
             dict(count=1, label="1M", step="month", stepmode="backward"),
             dict(count=3, label="3M", step="month", stepmode="backward"),
             dict(step="all", label="All")])
    fig.update_xaxes(title_text="時間 (UTC)",
                     rangeslider=dict(visible=True, thickness=0.06),
                     rangeselector=dict(buttons=btns, x=0, y=1.08,
                                        xanchor="left", yanchor="bottom",
                                        bgcolor="rgba(255,255,255,0.9)", activecolor="#E8EAF6"),
                     rangebreaks=brks, type="date", fixedrange=False)
    fig.update_yaxes(fixedrange=False, autorange=True)
    return fig


def build_candlestick_chart(ohlc: pd.DataFrame, industry: str, interval: str) -> go.Figure:
    chart = ohlc.copy()
    chart["MA20"] = chart["Close"].rolling(MA_SHORT, min_periods=1).mean()
    chart["MA50"] = chart["Close"].rolling(MA_LONG,  min_periods=1).mean()
    tf_label     = "日線" if interval == "1d" else "小時線"
    period_label = "4 個月" if interval == "1d" else "1 個月"
    fig = go.Figure()
    for idx_i, (y0, y1) in enumerate(_detect_bullish_fvg(chart)):
        fig.add_hrect(y0=y0, y1=y1, fillcolor="rgba(255,236,153,0.35)", line_width=0,
                      annotation_text="FVG" if idx_i == 0 else "",
                      annotation_position="right",
                      annotation=dict(font=dict(size=10, color="#8B6914")))
    fig.add_trace(go.Candlestick(
        x=chart.index, open=chart["Open"], high=chart["High"],
        low=chart["Low"], close=chart["Close"], name="等權重 K 線",
        increasing_line_color="#26A69A", decreasing_line_color="#EF5350",
    ))
    fig.add_trace(go.Scatter(x=chart.index, y=chart["MA20"], mode="lines", name="20 MA",
                             line=dict(color="#FB8C00", width=1.5)))
    fig.add_trace(go.Scatter(x=chart.index, y=chart["MA50"], mode="lines", name="50 MA",
                             line=dict(color="#1E88E5", width=1.5)))
    fig.update_layout(
        title=f"{industry} — 等權重 K 線（{tf_label} · 近 {period_label}）",
        yaxis_title="等權重指數（基期=100）",
        height=560, template="plotly_white",
        hovermode="x unified", dragmode="zoom",
        uirevision=f"{industry}-{interval}",
        legend=dict(orientation="h", yanchor="bottom", y=1.08, xanchor="right", x=1),
        margin=dict(t=80, b=60),
    )
    brks = [dict(bounds=["sat", "mon"])]
    if interval == "1h":
        brks.append(dict(bounds=[17, 9.5], pattern="hour"))
    btns = ([dict(count=5, label="5D", step="day", stepmode="backward"),
             dict(count=1, label="1M", step="month", stepmode="backward"),
             dict(step="all", label="All")] if interval == "1h" else
            [dict(count=5, label="5D", step="day", stepmode="backward"),
             dict(count=1, label="1M", step="month", stepmode="backward"),
             dict(count=3, label="3M", step="month", stepmode="backward"),
             dict(step="all", label="All")])
    fig.update_xaxes(title_text="時間 (UTC)",
                     rangeslider=dict(visible=True, thickness=0.08),
                     rangeselector=dict(buttons=btns, x=0, y=1.08,
                                        xanchor="left", yanchor="bottom",
                                        bgcolor="rgba(255,255,255,0.9)", activecolor="#E3F2FD"),
                     rangebreaks=brks, type="date", fixedrange=False)
    fig.update_yaxes(fixedrange=False, autorange=True)
    return fig


def build_momentum_chart(series: pd.DataFrame, industry: str) -> go.Figure:
    tail = series.dropna(subset=["VPMI_5D"]).tail(MOMENTUM_CHART_DAYS)
    fig  = go.Figure()
    fig.add_trace(go.Scatter(
        x=tail.index, y=tail["VPMI_5D"],
        mode="lines+markers", name="5日動能",
        line=dict(color="#6A1B9A", width=2), marker=dict(size=4),
    ))
    fig.add_hline(y=0, line_dash="dot", line_color="#999999")
    fig.update_layout(
        title=f"{industry} — 過去一個月 5 日滾動動能（VPMI）",
        xaxis_title="日期", yaxis_title="5日動能",
        height=320, template="plotly_white",
    )
    fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
    return fig


# ---------------------------------------------------------------------------
# 表格樣式
# ---------------------------------------------------------------------------
def style_metrics_table(df: pd.DataFrame) -> "pd.io.formats.style.Styler":
    NUM_COLS = ["最近交易日漲跌幅", "1日動能", "5日動能", "RS強弱", "MA50乖離率",
                "AlphaScore", "Alpha_Delta", "VPMI_v11_Score", "VP_Score", "MS_Score"]

    def _color(val: object) -> str:
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return "color: #888888"
        try:
            n = float(val)
        except (TypeError, ValueError):
            return ""
        if n > 0:  return "color: #2E7D32; font-weight:600"
        if n < 0:  return "color: #C62828; font-weight:600"
        return "color: #555555"

    display = df.copy()
    for col in NUM_COLS:
        if col not in display.columns:
            continue
        display[col] = display[col].map(
            lambda x: "N/A" if x is None or (isinstance(x, float) and np.isnan(x))
            else f"{x:+.2f}"
        )
    existing = [c for c in NUM_COLS if c in display.columns]
    styler   = display.style
    fn       = styler.map if hasattr(styler, "map") else styler.applymap
    return fn(_color, subset=existing)


# ---------------------------------------------------------------------------
# Streamlit UI
# ---------------------------------------------------------------------------
def main() -> None:
    st.set_page_config(
        page_title="台灣產業鏈監控 v11.2 · NBR 籌碼大腦",
        page_icon="🧠",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    if "nav" not in st.session_state:
        st.session_state.nav = "今日戰情"

    # ── 側邊欄：重新整理 / 資料狀態 ─────────────────────────────────────
    with st.sidebar:
        st.markdown("### 控制台")
        if st.button("🔄 強制重新整理數據", use_container_width=True, type="primary"):
            clear_data_caches()
            st.session_state.pop("data_loaded_at", None)
            st.rerun()
        st.caption("清除 yfinance / 法人 cache 後重抓（約需 1–3 分鐘）")
        st.divider()
        st.markdown("### 導航")
        st.radio(
            "頁面",
            options=NAV_OPTIONS,
            key="nav",
            label_visibility="collapsed",
        )
        st.divider()
        with st.expander("關於本系統", expanded=False):
            st.caption(
                f"yfinance + TWSE/TPEx 三大法人 · 近 {LOOKBACK_MONTHS} 個月日線 · "
                f"基準 {BENCHMARK} · TWD={USD_TWD} · .TW/.TWO 雙後綴已對齊"
            )

    st.title("🧠 台灣科技產業鏈監控")
    st.caption("Alpha v11.2 NBR 籌碼大腦戰情室")

    # ── 資料載入 ────────────────────────────────────────────────────────
    with st.spinner("正在載入三大法人資料（歷史 CSV + 今日即時爬蟲）…"):
        net_buy_df = load_net_buy_data()

    nbr_on = net_buy_df is not None
    if not nbr_on:
        st.warning(
            f"⚠️ 找不到 `{NET_BUY_CSV}`，以量能方向近似替代法人籌碼。"
            f"請執行 `python fetch_net_buy.py` 解鎖 NBR 全威力。"
        )

    with st.spinner("正在分批抓取台灣股市行情數據（含 SOXX 基準）…"):
        try:
            panels = fetch_market_data(ALL_TICKERS)
            calendar, aligned = align_panels(panels)
        except Exception as exc:
            st.error(f"數據獲取失敗：{exc}")
            return

    st.session_state["data_loaded_at"] = dt.datetime.now().strftime("%H:%M:%S")
    data_ts = st.session_state["data_loaded_at"]
    nbr_latest = (
        str(net_buy_df.index[-1].date()) if nbr_on and len(net_buy_df) else "—"
    )

    net_buy_aligned: dict[str, pd.Series] | None = None
    if net_buy_df is not None:
        try:
            nb_reindexed = net_buy_df.reindex(calendar).ffill().fillna(0)
            net_buy_aligned = build_net_buy_aligned(aligned, nb_reindexed)
        except Exception:
            net_buy_aligned = build_net_buy_aligned(aligned, None)
    else:
        net_buy_aligned = build_net_buy_aligned(aligned, None)

    try:
        industry_metrics: dict[str, pd.DataFrame] = {}
        for ind, tks in INDUSTRIES.items():
            try:
                industry_metrics[ind] = compute_industry_metrics(
                    ind, tks, aligned, net_buy_aligned
                )
            except ValueError:
                pass

        ma50_devs = {
            ind: compute_ma50_dev(
                tks, aligned,
                eq_cl=_top2_eq_close(industry_metrics[ind]) if ind in industry_metrics else None,
            )
            for ind, tks in INDUSTRIES.items()
        }
        rs_scores = {
            ind: compute_rs_slope(
                tks, aligned,
                eq_cl=_top2_eq_close(industry_metrics[ind]) if ind in industry_metrics else None,
            )
            for ind, tks in INDUSTRIES.items()
        }

        snapshot = latest_snapshot(industry_metrics, ma50_devs, rs_scores, aligned)
        snapshot = snapshot.sort_values("AlphaScore", ascending=False, na_position="last")
    except Exception as exc:
        st.error(f"指標計算失敗：{exc}")
        return

    _vix_today: float | None = None
    _vix_df = aligned.get("^VIX")
    if _vix_df is not None and "Close" in _vix_df.columns:
        _vix_close = _vix_df["Close"].dropna()
        if not _vix_close.empty:
            _vix_today = float(_vix_close.iloc[-1])

    _alpha_proxy = {
        ind: industry_metrics[ind]["VPMI_5D"].fillna(0.0)
        for ind in industry_metrics if "VPMI_5D" in industry_metrics[ind].columns
    }
    all_alpha_df = pd.DataFrame(_alpha_proxy).ffill() if _alpha_proxy else pd.DataFrame()

    if not all_alpha_df.empty and len(all_alpha_df) >= 6:
        _daily_b = (all_alpha_df.diff() > 0).sum(axis=1) / max(all_alpha_df.shape[1], 1)
        _b5d     = _daily_b.rolling(5, min_periods=1).mean()
        _breadth = float(
            (_b5d.rolling(20, min_periods=5).rank(pct=True) * 100).clip(0.0, 100.0).iloc[-1]
        )
    else:
        _breadth = 50.0

    _n_industries = max(len(industry_metrics), 1)

    if _vix_today is not None and _vix_today < 22.0:
        _gate_slots = 10
    elif _vix_today is not None and _vix_today < 25.0:
        _gate_slots = int(np.clip(np.floor(5 + _breadth / 15), 1, 9))
    else:
        _gate_slots = 1

    _gate_label = ("🚀 狂飆滿倉" if _gate_slots >= 8
                   else "🟢 防守回踩" if _gate_slots >= 4
                   else "❄️ 現金面壁")
    _vix_label  = (f"{_vix_today:.1f}  🔵 安全" if _vix_today is not None and _vix_today < 22.0
                   else f"{_vix_today:.1f}  ⚪ 震盪" if _vix_today is not None and _vix_today < 25.0
                   else f"{_vix_today:.1f}  🔴 恐慌" if _vix_today is not None
                   else "— (數據缺失)")

    top1_alpha = float(snapshot["AlphaScore"].max()) if not snapshot.empty else float("nan")
    top1_ind = (
        str(snapshot.loc[snapshot["AlphaScore"].idxmax(), "產業"])
        if not snapshot.empty else "—"
    )
    n_held_saved = len(st.session_state.get("holdings", load_saved_holdings()))

    # ── 首屏決策摘要 ────────────────────────────────────────────────────
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("控盤閘門", _gate_label, f"{_gate_slots} / 10 槽位")
    with m2:
        st.metric(
            "NBR 籌碼大腦",
            "啟動 ✅" if nbr_on else "退回量能 ⚠️",
            f"法人最新日 {nbr_latest}" if nbr_on else "請跑 fetch_net_buy.py",
        )
    with m3:
        st.metric(
            "Alpha Top 1",
            top1_ind if len(top1_ind) <= 10 else top1_ind[:9] + "…",
            f"α {top1_alpha:.1f}" if not np.isnan(top1_alpha) else "—",
        )
    with m4:
        st.metric("資料更新", data_ts, f"已記持股 {n_held_saved} 檔")

    if check_arbitrage_alert(snapshot):
        st.error(
            "🚨 **【設備端法人買超，注意下游製造端補漲】**："
            "上游晶圓廠設備/前段製程呈現法人集體建倉，"
            "請密切注意台灣代工、散熱、電源的突破機會。"
        )

    nav = st.session_state.nav

    # ══════════════════════════════════════════════════════════════════
    # 今日戰情
    # ══════════════════════════════════════════════════════════════════
    if nav == "今日戰情":
        st.subheader("🛡️ 全球位能防護閘門")
        _gc1, _gc2, _gc3 = st.columns(3)
        with _gc1:
            st.metric("VIX 恐慌指數", _vix_label, "< 22 安全 | 22–25 震盪 | ≥ 25 恐慌")
        with _gc2:
            st.metric("全球位能百分位", f"{_breadth:.1f} / 100",
                      f"5日平滑·20日歷史（{_n_industries} 産業）")
        with _gc3:
            st.metric("當前控盤水位", f"{_gate_slots} / 10", _gate_label)

        st.divider()
        render_sniper_scanner(snapshot)

        with st.expander("📖 Alpha v11.2 NBR 籌碼大腦 指標說明", expanded=False):
            st.markdown(
                """
                **Alpha Score v11.2 — NBR 籌碼大腦架構**

                | 層級 | 指標 | 權重 | 說明 |
                |------|------|------|------|
                | 核心 | **VPMI_v11_Score** | **80%** | NBR Barra (60%) + VPMI 20日自身歷史百分位 (40%) |
                | A-Tier | **MS_Score** | **15%** | MA 雙均線擴散歷史百分位 |
                | 輔助 | **VP_Score** | **5%** | 60日 Donchian 通道位置分 |

                **資料對齊**
                - `.TW` 上市 / `.TWO` 上櫃雙後綴
                - 歷史：`data/net_buy_shares.csv`
                - 持股記憶：`data/holdings.json`
                """
            )

    # ══════════════════════════════════════════════════════════════════
    # 持倉診斷
    # ══════════════════════════════════════════════════════════════════
    elif nav == "持倉診斷":
        render_position_diagnostics(snapshot, aligned, _gate_slots)

    # ══════════════════════════════════════════════════════════════════
    # 產業掃描
    # ══════════════════════════════════════════════════════════════════
    elif nav == "產業掃描":
        st.subheader("資金輪動四象限圖（法人 NBR 驅動）")
        try:
            st.plotly_chart(build_rotation_scatter(snapshot), use_container_width=True)
        except Exception as exc:
            st.warning(f"四象限圖無法顯示：{exc}")

        st.divider()
        st.subheader("全產業掃描")

        CORE_COLS = ["產業", "AlphaScore", "Alpha_Delta", "決策建議", "戰情燈號"]
        ADV_COLS = [
            "VPMI_v11_Score", "VP_Score", "MS_Score",
            "5日動能", "RS強弱", "MA50乖離率", "最近交易日漲跌幅", "1日動能",
        ]

        f1, f2, f3 = st.columns([2, 2, 2])
        with f1:
            signal_opts = sorted({
                str(s) for s in snapshot.get("戰情燈號", pd.Series(dtype=str)).dropna().unique()
            }) if "戰情燈號" in snapshot.columns else []
            signal_filter = st.multiselect(
                "燈號過濾",
                options=signal_opts,
                default=[],
                placeholder="全部燈號",
                key="signal_filter",
            )
        with f2:
            top_n = st.slider(
                "只看 Alpha Top N",
                min_value=5,
                max_value=max(len(snapshot), 5),
                value=min(20, max(len(snapshot), 5)),
                key="alpha_top_n",
            )
        with f3:
            show_advanced = st.toggle("顯示進階欄位", value=False, key="show_adv_cols")

        view = snapshot.copy()
        if signal_filter and "戰情燈號" in view.columns:
            view = view[view["戰情燈號"].isin(signal_filter)]
        view = view.head(top_n)

        show_cols = [c for c in CORE_COLS if c in view.columns]
        if show_advanced:
            show_cols += [c for c in ADV_COLS if c in view.columns and c not in show_cols]

        st.caption(f"顯示 {len(view)} / {len(snapshot)} 個產業")
        st.dataframe(
            style_metrics_table(view[show_cols]),
            use_container_width=True, hide_index=True,
        )

        jump_inds = list(view["產業"]) if "產業" in view.columns else []
        if jump_inds:
            jump = st.selectbox("快速跳到個股研究", options=["—"] + jump_inds, key="scan_jump")
            if jump != "—" and st.button("前往研究此產業 →", key="scan_jump_btn"):
                st.session_state["ind_sel"] = jump
                st.session_state["nav"] = "個股研究"
                st.rerun()

    # ══════════════════════════════════════════════════════════════════
    # 個股研究
    # ══════════════════════════════════════════════════════════════════
    elif nav == "個股研究":
        st.subheader("互動圖表 & SMC 個股分析")
        ind_options = list(INDUSTRIES.keys())
        if "ind_sel" in st.session_state and st.session_state.ind_sel not in ind_options:
            st.session_state.ind_sel = ind_options[0]

        ctrl_l, ctrl_r = st.columns([3, 2])
        with ctrl_l:
            selected = st.selectbox("選擇次產業", options=ind_options, key="ind_sel")
        with ctrl_r:
            timeframe = st.radio(
                "K 線週期", options=list(TIMEFRAME_OPTIONS.keys()),
                horizontal=True, key="chart_timeframe",
            )

        view_mode = st.radio(
            "顯示模式",
            options=["📊 產業等權重 K 線", "🔬 個股 SMC 精細分析"],
            horizontal=True, key="view_mode",
        )
        tf_cfg = TIMEFRAME_OPTIONS[timeframe]

        if view_mode == "📊 產業等權重 K 線":
            chart_tickers = tuple(sorted(INDUSTRIES[selected]))
            try:
                with st.spinner(f"正在載入 {timeframe} 等權重數據…"):
                    chart_panels  = fetch_chart_data(chart_tickers, tf_cfg["period"], tf_cfg["interval"])
                    chart_aligned = align_panels_utc(chart_panels)
                    ohlc = build_equal_weight_ohlc(
                        list(chart_tickers), chart_aligned,
                        filter_empty_bars=(tf_cfg["interval"] == "1h"),
                    )
                st.plotly_chart(
                    build_candlestick_chart(ohlc, selected, tf_cfg["interval"]),
                    use_container_width=True, config=PLOTLY_CHART_CONFIG,
                )
                if selected in industry_metrics:
                    st.plotly_chart(
                        build_momentum_chart(industry_metrics[selected], selected),
                        use_container_width=True,
                    )
            except Exception as exc:
                st.error(f"圖表繪製失敗：{exc}")
        else:
            ind_tickers = INDUSTRIES[selected]
            top_stocks  = get_stock_momentum_scores(ind_tickers, aligned, TOP_STOCKS_N)
            st.markdown("#### 動能前 3 強個股（依 VPMI_5D 排序）")
            rank_cols = st.columns(max(len(top_stocks), 1))
            for ri, (sym, vpmi) in enumerate(top_stocks):
                with rank_cols[ri]:
                    heat = ("🔴 極熱" if vpmi > 150 else "🟠 偏熱" if vpmi > 80
                            else "🟡 升溫" if vpmi > 0 else "🔵 冷卻")
                    st.metric(label=f"#{ri+1}  {sym}", value=f"{vpmi:+.1f}", delta=heat,
                              delta_color="off", help="個股 5 日 VPMI")

            if not ind_tickers:
                st.warning("此產業無可用標的。")
            else:
                top_syms   = [s for s, _ in top_stocks]
                other_syms = [s for s in ind_tickers if s not in top_syms]
                ordered    = top_syms + other_syms

                selected_stock = st.selectbox(
                    "選擇個股進行 SMC 分析", options=ordered, index=0, key="smc_stock_sel",
                    format_func=lambda s: (
                        f"⭐ {s}（動能 {next((v for k,v in top_stocks if k==s), 0):+.1f}）"
                        if s in top_syms else s
                    ),
                )

                stock_ohlc: pd.DataFrame | None = None
                if tf_cfg["interval"] == "1d":
                    stock_ohlc = _get_stock_ohlc(selected_stock, aligned, max_bars=90)
                else:
                    try:
                        with st.spinner(f"正在載入 {selected_stock} {timeframe} 數據…"):
                            sp = fetch_chart_data(
                                (selected_stock,), tf_cfg["period"], tf_cfg["interval"]
                            )
                            if selected_stock in sp:
                                stock_ohlc = sp[selected_stock][
                                    ["Open", "High", "Low", "Close"]
                                ].dropna(subset=["Close"])
                    except Exception:
                        pass

                if stock_ohlc is None or stock_ohlc.empty:
                    st.warning(f"{selected_stock} 無法取得 OHLC 數據。")
                else:
                    tf_lbl = "日線" if tf_cfg["interval"] == "1d" else "小時線"
                    chart_title = (
                        f"{selected_stock}  —  SMC 分析（{tf_lbl}）"
                        f"  |  OB=訂單塊  BOS=結構突破  Entry=進場訊號"
                    )
                    try:
                        fig_smc = build_smc_chart(stock_ohlc, chart_title, tf_cfg["interval"])
                        st.plotly_chart(
                            fig_smc, use_container_width=True, config=PLOTLY_CHART_CONFIG
                        )
                    except Exception as exc:
                        st.error(f"SMC 圖表繪製失敗：{exc}")
                    st.markdown(
                        "<div style='font-size:12px;color:#666;line-height:1.8;'>"
                        "🟪 <b>紫色矩形</b>：未觸及多頭訂單塊 ／ "
                        "🟨 <b>黃色帶狀</b>：看多失衡區 (FVG) ／ "
                        "🔵 <b>BOS↑</b>：向上結構突破 ／ "
                        "🔴 <b>BOS↓</b>：向下結構突破 ／ "
                        "🟢 <b>Entry ▲</b>：BOS 後回測 OB/FVG 進場機會"
                        "</div>", unsafe_allow_html=True,
                    )

    print(
        "\n  ✅ UI 優化版戰情室就緒！"
        f"導航={nav} · NBR={'ON' if nbr_on else 'OFF'} · 更新={data_ts}"
    )


if __name__ == "__main__":
    main()
