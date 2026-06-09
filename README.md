# amazon-inventory-profit-analyzer

一个本地 Streamlit Web 工具，用于上传亚马逊补货、库存、广告、利润 Excel，自动判断每个 SKU 的经营动作，并重点输出需要运营优先处理的 SKU、父体、SPU 和品线问题。

## 业务判断原则

1. 现金流健康高于短期利润。
2. 良性周转大于短期高毛利。
3. 高毛利但慢周转，不等于好 SKU。
4. 先排除不能补的，再找必须补的。
5. 补货建议必须结合库存、销量、广告、利润、库龄、父体、SPU、品线判断。
6. 主结果只聚焦头部重点问题、尾部异常、高毛利慢周转、紧急补货、清货停补、广告优化和维度汇总。

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
- `aged_inventory_181_plus`
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
- `广告花费` -> `ad_spend`
- `广告销售额` -> `ad_sales`
- `181以上库龄` -> `aged_inventory_181_plus`

如需兼容新字段名，只需要在对应标准字段的 `aliases` 中增加名称。

## 输出 Sheet 说明

导出的 Excel 包含：

1. `01_总览`
2. `02_头部重点问题SKU`
3. `03_尾部异常SKU`
4. `04_高毛利慢周转SKU`
5. `05_紧急补货SKU`
6. `06_清货停补SKU`
7. `07_广告优化SKU`
8. `08_SKU完整判断`
9. `09_父体分析`
10. `10_父体结构异常`
11. `11_SPU分析`
12. `12_品线分析`
13. `13_数据异常`

## 判断逻辑说明

每个 SKU 只输出一个主动作 `final_action`，并带有 `priority` 和中文 `reason`。判断顺序以现金流和利润安全为先：

1. 清货处理
2. 禁止补货
3. 暂缓补货
4. 控广告
5. 高毛利库存可控时加大投入加速周转
6. 高毛利慢周转时控补货促周转
7. 高毛利严重慢周转时停补
8. 立即补货 / 优先补货
9. 正常补货 / 谨慎补货
10. 可加广告
11. 观察

注意：工具不会因为 `recommended_replenishment_qty` 大就直接建议补货。若利润、广告或现金流不健康，会覆盖补货建议。

利润正负判断以 `order_gross_profit` 为准；`order_gross_margin` 仍用于高毛利分层和 ACOS 安全线对比。

## 如何调整 thresholds.yaml

阈值集中在 `config/thresholds.yaml`：

- `inventory`：缺货、健康库存、慢周转、清货天数阈值。
- `margin`：高/中/低毛利阈值。
- `cashflow`：良性周转和高毛利慢周转阈值。
- `ads`：广告异常阈值。
- `ranking`：头部 Top 百分比和尾部 Top N。

修改后重启 Streamlit 即可生效。

## 常见问题

**上传后字段缺失怎么办？**  
页面会提示缺失的必填字段，并在 `数据异常` 表中记录。可在 `column_mapping.yaml` 增加字段别名。

**表格前面有汇总行会不会读错？**  
工具会扫描前几行并自动识别真实表头，样例表的第三行表头可直接识别。

**毛利率是 30、30%、0.3 都支持吗？**  
支持。清洗后统一转换为 `0.3`。

**为什么高毛利 SKU 也会停补？**  
高毛利但库存天数过长会占用现金流。超过 180 天会提示停补或控补货，超过 270 天优先清货。

**为什么完整 SKU 表不是第一页？**  
工具定位是经营动作判断，主结果优先展示重点问题和异常 SKU，完整表保留在后续页面和导出 Sheet 中。
