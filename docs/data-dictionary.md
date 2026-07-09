# 数据字典

完整字段别名和数据类型以 `config/column_mapping.yaml` 为准。本文件记录核心标准字段及业务口径。

## 标识与维度

| 字段 | 含义 | 要求/说明 |
|---|---|---|
| `sku` | 店铺 SKU | 必填；主要行动对象 |
| `asin` | 子 ASIN | 可选；支持筛选 |
| `parent_asin` | 父 ASIN | 可选；角色和父体比较依赖此字段 |
| `spu` | SPU | 可选；用于 SPU 聚合 |
| `product_line` | 品线 | 可选；Fang 品线诊断依赖此字段 |
| `category_level_1` | 一级分类 | 可选；也参与品线维度聚合 |
| `category_level_3` | 三级分类 | 可选；用于侧边栏联动筛选和 SKU 明细输出，筛选器显示名称为“尺寸” |
| `size` | 尺寸/规格 | 可选；缺失时同规格比较降为低置信度 |
| `product_name` | 产品名称 | 可选 |

## 必填经营输入

| 字段 | 含义 | 标准口径 |
|---|---|---|
| `predicted_daily_sales` | 预测日销量 | 数量 |
| `stock_days` | 原表库存天数 | 数值；系统另算可售库存天数 |
| `recommended_replenishment_qty` | 原表建议补货量 | 数量；不能独立决定补货 |
| `sales_7d_units` | 7 天销量 | 数量 |
| `sales_14d_units` | 14 天销量 | 数量 |
| `order_gross_profit` | 订单毛利润 | 金额；利润正负的主要依据 |
| `order_gross_margin` | 订单毛利率 | 清洗后以小数保存，如 30% 为 `0.3` |
| `ad_spend` | 广告花费 | 金额 |
| `ad_sales` | 广告销售额 | 金额 |
| `acos` | 广告销售成本比 | 百分比小数 |

库存字段还要求 `total_supply_qty` 或 `available_qty` 至少存在一个。

## 库存输入

| 字段 | 含义 |
|---|---|
| `total_supply_qty` | 总供给/总库存 |
| `available_qty` | 可用/可售库存 |
| `inbound_qty` | 在途库存 |
| `inventory_value` | 库存金额 |
| `aged_inventory_90_plus` | 90 天以上库龄合计 |
| `aged_inventory_91_180` | 91-180 天库龄 |
| `aged_inventory_181_plus` | 181 天以上库龄汇总回退字段 |
| `aged_inventory_181_270` | 181-270 天库龄 |
| `aged_inventory_271_330` | 271-330 天库龄 |
| `aged_inventory_331_365` | 331-365 天库龄 |
| `aged_inventory_365_plus` | 365 天以上库龄 |

若 `aged_inventory_90_plus` 原始值存在，优先使用；否则按 91-180 与 181+ 分桶合计。

## 销售与流量输入

| 字段 | 含义/回退规则 |
|---|---|
| `sales_7d_amount` | 7 天销售额 |
| `sales_14d_amount` | 14 天销售额；页面切到 14 天时作为当前周期总销售额 |
| `ad_impressions` | 广告曝光 |
| `ad_clicks` | 广告点击 |
| `ad_orders` | 广告订单 |
| `total_orders` | 总订单；无有效值时回退 14 天销量 |
| `sessions_7d` | 7 天会话数 |
| `sessions_14d` | 14 天会话数 |
| `cpc` | CPC；缺失时可计算 |
| `ctr` | CTR；缺失时可计算 |
| `cvr` | 总转化率；缺失时可计算 |
| `ad_cvr` | 广告转化率；缺失时可计算 |
| `acoas` | 原表 ACOAS 可映射，但页面和报告会按广告花费/当前周期总销售额重新计算 |

## 主要派生字段

| 字段 | 公式/含义 |
|---|---|
| `avg_sales_7d` | `sales_7d_units / 7` |
| `avg_sales_14d` | `sales_14d_units / 14` |
| `main_daily_sales` | 7 天日均、14 天日均×0.8、预测日销量中的最大值 |
| `available_stock_qty` | 可售库存；缺失时回退总供给减在途 |
| `available_stock_days` | 可售库存 / 7 天日均销量 |
| `inbound_stock_days` | 在途库存 / 7 天日均销量 |
| `ideal_turnover_daily_units` | 可售库存 / 理想周转天数，默认 90 天 |
| `over_90_stock_qty` | 超过理想周转需求的可售库存量 |
| `over_90_inventory_ratio` | 90 天以上库存量 / 可售库存量 |
| `ad_order_share` | 广告订单 / 总订单 |
| `selected_sales_units` | 当前页面周期销量；7 天或 14 天快速周期切换决定 |
| `selected_sales_amount` | 当前页面周期销售额；用于当前口径 ACOAS 分母 |
| `selected_daily_sales_units` | 当前页面周期销量 / 周期天数 |
| `acoas` | 广告花费 / 当前周期总销售额；筛选后按可见范围重新汇总 |
| `margin_level` | 毛利率分层 |
| `turnover_level` | 周转分层 |
| `inventory_status` | 库存风险状态 |
| `profit_status` | 毛利润状态 |
| `ad_status` | 广告健康状态 |
| `cashflow_risk_level` | 现金流风险等级 |
| `sku_role` | 四类互斥 SKU 经营角色 |
| `final_action` | SKU 唯一系统主动作 |
| `priority` | 系统动作优先级 |
| `reason` | 系统动作原因 |

## 缺失值约定

- 清洗阶段会生成 `_missing_<field>` 标记，表示原始单元格是否缺失。
- 部分数量和金额字段为了计算会补为 0；判断数据完整性时必须同时查看 `_missing_` 标记，不能仅检查清洗后的数值列。
- 缺少原始字段与字段存在但单元格为空是不同情况；映射报告记录前者，`_missing_` 标记记录后者。
