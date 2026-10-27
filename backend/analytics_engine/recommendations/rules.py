"""Recommendation rules: finding types -> issue, action (per business type), KPI.

Each rule fires only when at least one finding of its types has a severity above "info".
Data-quality rules (complete the expense list, fix flagged records, widen data coverage) have no
``expected_direction``: they make results measurable rather than move a business metric.
Wording is deliberately conditional ("review", "consider", "aim to"): the engine suggests
what to look at, it never promises an outcome. Actions differ for retail / service / other
(the generic ``other`` text is used for any unknown business type).

To add a rule: add a ``Rule`` to ``RULES`` and make sure the finding type it listens to is
produced by a ``*/findings.py`` builder (a test checks this).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    id: str
    types: tuple[str, ...]          # finding types that trigger the rule
    issue: str
    actions: dict[str, str]         # keys: retail, service, other
    kpi: str
    supporting_metric: str
    expected_metric: str | None     # metric we aim to move (None for data-quality actions)
    direction: str | None           # "increase" | "decrease" (None for data-quality actions)


RULES: tuple[Rule, ...] = (
    Rule("EXPENSE-LIST", ("expense_definition_incomplete",),
         "Profit cannot be calculated because the expense list is not marked complete.",
         {"retail": "List every cost of running the shop (stock purchases, rent, salaries, electricity, "
                    "transport, loan interest, taxes), then mark the expense list as complete so real profit can be measured.",
          "service": "List every cost of delivering your services (staff pay, rent, tools and software, travel, "
                     "marketing, taxes), then mark the expense list as complete so real profit can be measured.",
          "other": "List all the costs of running the business, then mark the expense list as complete so "
                   "real profit can be measured."},
         "Whether profit can be calculated (all costs listed and marked complete)",
         "revenue_minus_listed_expenses", None, None),
    Rule("LOSS", ("profit_margin_level", "loss_months"),
         "Profit is thin or negative, or monthly costs exceeded revenue.",
         {"retail": "Review selling prices against purchase costs on the main products, check supplier prices, "
                    "wastage and discounts, and look at which monthly costs are highest in the loss-making months.",
          "service": "Review your service prices or hourly rates against the time and costs each job takes, check "
                     "unbilled time and discounts, and look at which monthly costs are highest in the loss-making months.",
          "other": "Review prices against costs and look at which monthly costs are highest in the loss-making months."},
         "Profit margin (%) and number of months with costs above revenue", "profit_margin_pct",
         "profit_margin_pct", "increase"),
    Rule("COSTS", ("expenses_outpacing_revenue",),
         "Costs are growing faster than sales.",
         {"retail": "Compare each cost line with last year to find what grew fastest (purchase prices, wastage, rent, "
                    "wages) and review it every month.",
          "service": "Compare each cost line with last year to find what grew fastest (staff hours, subcontractors, "
                     "tools, travel) and review it every month.",
          "other": "Compare each cost line with last year to find what grew fastest and review it every month."},
         "Gap between expense growth and revenue growth (percentage points)",
         "listed_expenses_trend_pct_per_month", "listed_expenses_trend_pct_per_month", "decrease"),
    Rule("REVENUE-DECLINE", ("revenue_decline_yoy", "revenue_trend_decreasing", "revenue_decline_mom",
                             "revenue_growth_12m"),
         "Revenue is falling compared with earlier periods.",
         {"retail": "Check what changed: footfall, stock availability, prices compared with nearby competitors, "
                    "and whether the same months fell last year (seasonality) before deciding on action.",
          "service": "Check what changed: repeat clients, new enquiries and referrals, available capacity, and "
                     "whether the same months fell last year (seasonality) before deciding on action.",
          "other": "Check what changed in customers, prices and capacity, and whether the same months fell last "
                   "year (seasonality) before deciding on action."},
         "Monthly revenue compared with the same month last year (%)", "revenue_yoy_pct",
         "revenue_yoy_pct", "increase"),
    Rule("VOLATILITY", ("revenue_volatility",),
         "Monthly revenue swings a lot, which makes cash planning harder.",
         {"retail": "Plan stock and cash for the weak months, and consider promotions or bundles to lift slow months.",
          "service": "Consider retainers, prepaid packages or scheduled repeat work to even out income, and keep a "
                     "cash reserve for slow months.",
          "other": "Keep a cash reserve for slow months and look for ways to even out income across the year."},
         "Month-to-month variation in revenue (%)", "revenue_cv", "revenue_cv", "decrease"),
    Rule("CUSTOMER-RETENTION", ("repeat_customers_low", "customer_retention_low"),
         "Too few customers come back.",
         {"retail": "Follow up with first-time buyers (reminders, a small return offer, a loyalty card) and find out "
                    "why lapsed customers stopped buying.",
          "service": "Offer to rebook before the customer leaves, send reminders, consider prepaid packages, and ask "
                     "lapsed clients why they stopped.",
          "other": "Follow up with first-time customers and find out why lapsed customers stopped buying."},
         "Repeat customer rate (%) and monthly retention (%)", "repeat_customer_rate_pct",
         "repeat_customer_rate_pct", "increase"),
    Rule("CUSTOMER-DECLINE", ("active_customers_decreasing",),
         "The number of active customers is falling.",
         {"retail": "Reach out to customers who have not bought recently, and ask current customers for referrals.",
          "service": "Contact clients who have not booked recently, and ask current clients for referrals.",
          "other": "Contact customers who have not bought recently, and ask current customers for referrals."},
         "Active customers per month", "active_customers_trend_pct_per_month",
         "active_customers_trend_pct_per_month", "increase"),
    Rule("CUSTOMER-CONCENTRATION", ("customer_concentration",),
         "A few customers account for a large share of spending.",
         {"retail": "Look after your biggest customers (reliable stock, service) and work on widening the customer base "
                    "so no single customer's loss would hurt badly.",
          "service": "Look after your biggest clients (agreements, regular check-ins) and work on widening the client "
                     "base so no single client's loss would hurt badly.",
          "other": "Look after your biggest customers and work on widening the customer base."},
         "Largest customer's share of spend (%)", "top_customer_share_pct",
         "top_customer_share_pct", "decrease"),
    Rule("PRODUCT-MARGIN", ("negative_margin_product", "low_margin_main_product"),
         "Some products or services earn little or lose money on each sale.",
         {"retail": "For the products named in the evidence, compare selling price with purchase cost, ask suppliers "
                    "for better terms, or consider raising the price or dropping the item.",
          "service": "For the services named in the evidence, compare the price with the time and cost to deliver, "
                     "and consider repricing, bundling or dropping them.",
          "other": "For the items named in the evidence, compare price with cost and consider repricing or dropping them."},
         "Gross margin (%) of the named products", "gross_margin_pct", "gross_margin_pct", "increase"),
    Rule("PRODUCT-CONCENTRATION", ("product_concentration",),
         "One product brings a large share of revenue.",
         {"retail": "Keep the top seller reliably in stock and look for a second and third product that could "
                    "grow, so the shop depends less on a single item.",
          "service": "Protect your main service and look for additional services that could grow, so income depends "
                     "less on one offering.",
          "other": "Protect the main product and look for others that could grow."},
         "Best-selling product's share of revenue (%)", "top_product_share_pct",
         "top_product_share_pct", "decrease"),
    Rule("PRODUCT-DECLINE", ("product_revenue_declining", "product_losing_share"),
         "Some products are selling less or losing share.",
         {"retail": "For each product named in the evidence, check price, stock availability and local demand, and "
                    "decide whether to promote it, reprice it or phase it out.",
          "service": "For each service named in the evidence, check price, availability and demand, and decide "
                     "whether to promote, reprice or retire it.",
          "other": "For each item named in the evidence, check price, availability and demand, and decide whether to "
                   "promote, reprice or phase it out."},
         "Monthly revenue of the named products", "revenue_trend_pct_per_month",
         "revenue_trend_pct_per_month", "increase"),
    Rule("LOW-CONTRIBUTION", ("low_contribution_products",),
         "Several products each bring very little revenue.",
         {"retail": "Review the smallest sellers: they may tie up stock and shelf space. Consider ordering less of "
                    "them or removing the ones with weak margins.",
          "service": "Review the smallest services: consider bundling them with popular ones or retiring those "
                     "that take effort for little income.",
          "other": "Review the smallest sellers and consider keeping only those that earn their place."},
         "Number of products under 5% of revenue", "products_below_5pct_share",
         "products_below_5pct_share", "decrease"),
    Rule("DATA-COVERAGE", ("customer_data_coverage_low", "product_data_coverage_low"),
         "Customer or product records cover only part of the business.",
         {"retail": "Record all sales by customer and product so these insights describe the whole shop.",
          "service": "Record all jobs by client and service so these insights describe the whole business.",
          "other": "Record all sales by customer and product so these insights describe the whole business."},
         "Share of revenue covered by customer / product records (%)", "customer_data_coverage_pct",
         None, None),
    Rule("DATA-REVIEW", ("data_needs_review",),
         "Some records have unusual values that may distort the results.",
         {"retail": "Check the flagged months or rows (refunds, typing errors, one-off large sales), then correct "
                    "them or confirm they are genuine.",
          "service": "Check the flagged months or rows (refunds, typing errors, one-off large jobs), then correct "
                     "them or confirm they are genuine.",
          "other": "Check the flagged records, then correct them or confirm they are genuine."},
         "Number of flagged records", "flagged_months", None, None),
)
