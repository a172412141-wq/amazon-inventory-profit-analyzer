# amazon-inventory-profit-analyzer

一个本地 Streamlit Web 工具，用于上传亚马逊补货、库存、广告、利润 Excel，自动判断每个 SKU 的经营动作，并重点输出需要运营优先处理的 SKU、父体、SPU 和品线问题。

## 业务判断原则

1. 现金流健康高于短期利润。
2. 良性周转大于短期高毛利。
3. 高毛利但慢周转，不等于好 SKU。
4. 先排除不能补的，再找必须补的。
5. 补货建议必须结合库存、销量、广告、利润、库龄、父体、SPU、品线判断。
6. 主结果按引流 SKU、主力 SKU、利润 SKU、低效异常 SKU 四类经营角色聚焦展示，同时保留补货、清货、控广告等主动作判断。

## 安装方式

```bash
pip install -r requirements.txt
```

## 运行方式

```bash
streamlit run app.py
```

## 输入 Excel 字段要求

最低必填字段：

- `sku`
- `predicted_daily_sales`
- `stock_days`
- `recommended_replenishment_qty`
- `total_supply_qty` 或 `available_qty`
- `sales_7d_units`
- `sales_14d_units`
- `order_gross_profit`
- `order_gross_margin`
- `ad_spend`
- `ad_sales`
- `acos`

可选增强字段：

- `parent_asin`
- `spu`
- `product_line`
- `category_level_1`
- `sales_7d_amount`
- `sales_14d_amount`
- `ad_impressions`
- `ad_clicks`
- `ad_orders`
- `total_orders`
- `cpc`
- `ctr`
- `cvr`
- `ad_cvr`
- `acoas`（系统会按 `ad_spend / 总销售额` 自动计算）
- `sessions_7d`
- `sessions_14d`
- `aged_inventory_90_plus`
- `aged_inventory_181_plus`
- `aged_inventory_91_180`
- `aged_inventory_181_270`
- `aged_inventory_271_330`
- `aged_inventory_331_365`
- `aged_inventory_365_plus`
- `inbound_qty`
- `inventory_value`

## 字段映射说明

字段映射在 `config/column_mapping.yaml` 中维护。工具内部统一使用标准英文字段，上传表格可以是中文字段。当前已适配样例表 `智能补货表 (6).xlsx` 的字段，例如：

- `预测日销量` -> `predicted_daily_sales`
- `预计可售天数` -> `stock_days`
- `建议补货量` -> `recommended_replenishment_qty`
- `总供给` -> `total_supply_qty`
- `可用量` -> `available_qty`
- `7天订单商品总数` -> `sales_7d_units`
- `14天订单商品总数` -> `sales_14d_units`
- `订单毛利率` -> `order_gross_margin`
- `广告曝光量` -> `ad_impressions`
- `广告点击数` -> `ad_clicks`
- `广告订单` -> `ad_orders`
- `14天订单商品总数` -> `total_orders`
- `CPC` -> `cpc`
- `CTR` -> `ctr`
- `14天销售转化率` -> `cvr`
- `广告CVR` -> `ad_cvr`
- `ACOAS` -> `acoas`
- `14天会话数` -> `sessions_14d`
- `广告花费` -> `ad_spend`
- `广告销售额` -> `ad_sales`
- `库龄超过90天合计数量` -> `aged_inventory_90_plus`
- `91~180库龄` -> `aged_inventory_91_180`
- `181~270库龄` -> `aged_inventory_181_270`
- `271~330库龄` -> `aged_inventory_271_330`
- `331~365库龄` -> `aged_inventory_331_365`
- `365以上库龄` -> `aged_inventory_365_plus`
- `181以上库龄` -> `aged_inventory_181_plus`

如需兼容新字段名，只需要在对应标准字段的 `aliases` 中增加名称。

## 输出 Sheet 说明

导出的 Excel 包含：

1. `01_总览`
2. `02_引流SKU`
3. `03_主力SKU`
4. `04_利润SKU`
5. `05_低效异常SKU`
6. `06_SKU完整判断`
7. `07_父体分析`
8. `08_父体结构异常`
9. `09_SPU分析`
10. `10_品线分析`
11. `11_数据异常`

## 判断逻辑说明

每个 SKU 只输出一个主动作 `final_action`，并带有 `priority` 和中文 `reason`。周转判断优先使用 `available_stock_days`，计算公式为 `可售库存 / 7天平均日销量`；没有可售库存字段时才回退到表内 `stock_days`。判断顺序先看周转，再看利润和广告：

1. 180 天以上可售库存为超红线，P0 清货处理。
2. 91-180 天可售库存为红线，P0 禁止补货并处理周转。
3. 61-90 天可售库存需结合在途库存加急清理，并测算目标日销量。
4. 毛利润为负时暂缓补货或清货。
5. 广告无转化、ACOS 超过毛利率时控广告；ACOAS 按 `广告花费 / 总销售额` 展示整体广告花费占销售额比例。
6. 高毛利且库存仍可控时加大投入加速周转。
7. 高毛利但库存红线时优先现金流，不能继续补货。
8. 立即补货 / 优先补货
9. 正常补货 / 谨慎补货
10. 可加广告
11. 观察

注意：工具不会因为 `recommended_replenishment_qty` 大就直接建议补货。若利润、广告或现金流不健康，会覆盖补货建议。

利润正负判断以 `order_gross_profit` 为准；`order_gross_margin` 仍用于毛利率分层和 ACOS 安全线对比。毛利率分层为：0%-8% 低毛利率水平，8%-15% 中毛利率水平，15%+ 高毛利率水平。

## SKU 经营角色分类

SKU 经营角色用 `sku_role` 表示，只能是以下四类之一：

- `引流 SKU`
- `主力 SKU`
- `利润 SKU`
- `低效异常 SKU`

角色分类不替代 `final_action`。`sku_role` 用来判断 SKU 在父体内承担什么经营角色；`final_action` 仍用来表达立即补货、控广告、清货处理、观察等具体动作。

角色判断基于 `parent_asin` 父体维度的相对表现。系统会计算父体内广告花费占比、父体平均日均销量、父体毛利率，并输出：

- `sku_role_candidates`：候选标签，允许一个 SKU 同时具备多个候选特征。
- `sku_role_reason`：中文解释，说明为什么归入该角色。

最终 `sku_role` 互斥，候选特征可以多命中，最终分类按以下顺序判断：

1. `引流 SKU`：广告花费占父体总花费 `> 35%`
2. `主力 SKU`：日均销量高于父体内所有子 SKU 的日均销量算术平均值，且毛利率高于父体毛利率
3. `利润 SKU`：毛利率高于父体毛利率 `50%` 以上
4. `低效异常 SKU`：不满足上述三类条件

父体日均销量平均值按每个 `parent_asin` 单独分组计算，使用子 SKU 指标值的算术平均，不使用合计值。例如同一父体下两个子 SKU 的日均销量为 4 和 6，则父体平均日均销量为 5。父体毛利率按 `父体下所有子体毛利润之和 / 父体下所有子体销售额之和` 计算。

总览 Dashboard 会展示 CPC、CTR、CVR、广告CVR、ACOS、ACOAS、广告订单占比、可售库存天数、在途库存天数、库龄超过90天合计数量，以及 61-90 天、91-180 天、180 天以上可售库存量。广告订单占比公式为 `广告订单 / 总订单`，总订单优先读取原表字段，没有时使用 `14天订单商品总数`。ACOAS 公式为 `广告花费 / 总销售额`，总销售额优先使用 `14天销售额`，缺失时使用 `7天销售额`。其中 CPC/CTR/CVR 优先使用原表字段；如果原表缺失，会按广告点击、曝光、会话、广告订单等字段自动计算。

## 如何调整 thresholds.yaml

阈值集中在 `config/thresholds.yaml`：

- `inventory`：缺货、健康库存、61-90 加急、91-180 红线、180+ 超红线阈值。
- `margin`：高/中/低毛利阈值，默认 8% 和 15%。
- `cashflow`：良性周转和高毛利慢周转阈值。
- `ads`：广告异常阈值。
- `ranking`：头部 Top 百分比和尾部 Top N。
- `sku_roles`：引流广告花费占比阈值和利润 SKU 毛利率倍数阈值。

修改后页面重新运行即可生效；如果部署在 Streamlit Cloud，保存配置并触发一次重新部署即可刷新缓存。

## 常见问题

**上传后字段缺失怎么办？**  
页面会提示缺失的必填字段，并在 `数据异常` 表中记录。可在 `column_mapping.yaml` 增加字段别名。

**表格前面有汇总行会不会读错？**  
工具会扫描前几行并自动识别真实表头，样例表的第三行表头可直接识别。

**毛利率是 30、30%、0.3 都支持吗？**  
支持。清洗后统一转换为 `0.3`。

**为什么高毛利 SKU 也会停补？**  
高毛利但可售库存天数过长会占用现金流。超过 90 天进入库存红线，超过 180 天进入超红线，优先停补、清货和加速周转。

**为什么完整 SKU 表不是第一页？**  
工具定位是经营动作判断，主结果优先展示四类 SKU 经营角色，完整表保留在后续页面和导出 Sheet 中。
