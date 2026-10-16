"""
The Stock Bet - reference solution for Case 1
Applied Finance with Python

Run with:
    pip install -r requirements.txt
    streamlit run app.py
"""

from dataclasses import dataclass
from datetime import date, timedelta

import altair as alt
import pandas as pd
import streamlit as st
import yfinance as yf

# --------------------------------------------------------------------------
# Page setup
# --------------------------------------------------------------------------
st.set_page_config(page_title="The Stock Bet", page_icon="📈", layout="wide")

MIA_COLOR = "#2F6F9F"
TOM_COLOR = "#E8923F"

# Reference prices (Xetra close, EUR) used only if the live download fails.
# Allianz start price is an approximation - verify before relying on it.
FALLBACK = {
    "Mia": {"buy": 194.00, "sell": 413.10},
    "Tom": {"buy": 135.66, "sell": 273.85},
}


# --------------------------------------------------------------------------
# Finance logic (pure functions, no Streamlit)
# --------------------------------------------------------------------------
@dataclass
class Result:
    name: str
    ticker: str
    buy_date: pd.Timestamp
    sell_date: pd.Timestamp
    buy_price: float
    sell_price: float
    amount: float

    @property
    def shares(self) -> float:
        return self.amount / self.buy_price

    @property
    def final_value(self) -> float:
        return self.shares * self.sell_price

    @property
    def profit(self) -> float:
        return self.final_value - self.amount

    @property
    def total_return(self) -> float:
        return self.final_value / self.amount - 1

    @property
    def years(self) -> float:
        return (self.sell_date - self.buy_date).days / 365.25

    @property
    def cagr(self) -> float:
        return (self.final_value / self.amount) ** (1 / self.years) - 1

    @property
    def naive_annual(self) -> float:
        """The common mistake: total return divided by the number of years."""
        return self.total_return / self.years


def first_on_or_after(prices: pd.Series, day: date) -> tuple[pd.Timestamp, float]:
    s = prices[prices.index >= pd.Timestamp(day)]
    if s.empty:
        raise ValueError(f"No trading day on or after {day}.")
    return s.index[0], float(s.iloc[0])


def last_on_or_before(prices: pd.Series, day: date) -> tuple[pd.Timestamp, float]:
    s = prices[prices.index <= pd.Timestamp(day)]
    if s.empty:
        raise ValueError(f"No trading day on or before {day}.")
    return s.index[-1], float(s.iloc[-1])


@st.cache_data(ttl=3600, show_spinner=False)
def load_prices(ticker: str, start: date, end: date) -> pd.DataFrame:
    """Daily prices from Yahoo Finance. Tickers ending in .DE are Xetra quotes."""
    df = yf.Ticker(ticker).history(
        start=start - timedelta(days=10),
        end=end + timedelta(days=1),  # end date is exclusive in yfinance
        auto_adjust=False,
    )
    if df.empty:
        raise ValueError(f"No data returned for {ticker}.")
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    if "Adj Close" not in df.columns:
        df["Adj Close"] = df["Close"]
    return df[["Close", "Adj Close"]]


def fmt_eur(x: float) -> str:
    return f"€{x:,.2f}"


def fmt_pct(x: float, signed: bool = False) -> str:
    return f"{x:+.1%}" if signed else f"{x:.1%}"


# --------------------------------------------------------------------------
# Sidebar: the case parameters
# --------------------------------------------------------------------------
with st.sidebar:
    st.header("Case settings")
    amount = st.number_input("Amount invested by each (€)", min_value=100.0, value=1000.0, step=100.0)

    st.subheader("Mia")
    mia_ticker = st.text_input("Ticker", "ALV.DE", key="mia_t", help="ALV.DE = Allianz SE on Xetra")
    mia_buy = st.date_input("Bought on", date(2021, 9, 30), key="mia_d")

    st.subheader("Tom")
    tom_ticker = st.text_input("Ticker", "SIE.DE", key="tom_t", help="SIE.DE = Siemens AG on Xetra")
    tom_buy = st.date_input("Bought on", date(2023, 9, 29), key="tom_d")

    st.subheader("Settling the bet")
    settle = st.date_input("Settlement date", date(2026, 9, 23))

    basis = st.radio(
        "Price basis",
        ["Closing price", "Adjusted close"],
        help="Closing price = share price only. Adjusted close also includes dividends, "
             "assuming they were reinvested.",
    )
    col = "Close" if basis == "Closing price" else "Adj Close"

# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------
live = True
series = {}
try:
    with st.spinner("Downloading prices from Yahoo Finance..."):
        mia_df = load_prices(mia_ticker, mia_buy, settle)
        tom_df = load_prices(tom_ticker, tom_buy, settle)
    mia_bd, mia_bp = first_on_or_after(mia_df[col], mia_buy)
    mia_sd, mia_sp = last_on_or_before(mia_df[col], settle)
    tom_bd, tom_bp = first_on_or_after(tom_df[col], tom_buy)
    tom_sd, tom_sp = last_on_or_before(tom_df[col], settle)
    series = {"Mia": mia_df[col], "Tom": tom_df[col]}
except Exception as err:  # network problems, unknown ticker, ...
    live = False
    st.warning(
        f"Live prices could not be loaded ({err}). Enter the prices manually below - "
        "the fields are pre-filled with reference values (Xetra close)."
    )
    c1, c2 = st.columns(2)
    with c1:
        mia_bp = st.number_input("Mia: buy price (€)", value=FALLBACK["Mia"]["buy"])
        mia_sp = st.number_input("Mia: price on settlement date (€)", value=FALLBACK["Mia"]["sell"])
    with c2:
        tom_bp = st.number_input("Tom: buy price (€)", value=FALLBACK["Tom"]["buy"])
        tom_sp = st.number_input("Tom: price on settlement date (€)", value=FALLBACK["Tom"]["sell"])
    mia_bd, tom_bd = pd.Timestamp(mia_buy), pd.Timestamp(tom_buy)
    mia_sd = tom_sd = pd.Timestamp(settle)

mia = Result("Mia", mia_ticker, mia_bd, mia_sd, mia_bp, mia_sp, amount)
tom = Result("Tom", tom_ticker, tom_bd, tom_sd, tom_bp, tom_sp, amount)

# --------------------------------------------------------------------------
# Header
# --------------------------------------------------------------------------
st.title("The Stock Bet")
st.markdown(
    f"Mia invested **{fmt_eur(amount)}** in **{mia.ticker}** on {mia_buy:%d %B %Y}. "
    f"Tom invested **{fmt_eur(amount)}** in **{tom.ticker}** on {tom_buy:%d %B %Y}. "
    f"On {settle:%d %B %Y} they settle their bet."
)
st.caption(f"Price basis: {basis.lower()}. Buy and sell at the closing price of the nearest trading day.")

# --------------------------------------------------------------------------
# Question 1
# --------------------------------------------------------------------------
st.header("1. Who made the better investment?")

c1, c2 = st.columns(2)
for c, r in ((c1, mia), (c2, tom)):
    with c:
        st.subheader(r.name)
        m1, m2, m3 = st.columns(3)
        m1.metric("Final value", fmt_eur(r.final_value))
        m2.metric("Profit", fmt_eur(r.profit), fmt_pct(r.total_return, signed=True))
        m3.metric("Holding period", f"{r.years:.2f} years")
        st.caption(
            f"Bought {r.shares:.3f} shares at {fmt_eur(r.buy_price)} on {r.buy_date:%d.%m.%Y}, "
            f"worth {fmt_eur(r.sell_price)} each on {r.sell_date:%d.%m.%Y}."
        )

# Value of the investment over time
if live:
    frames = []
    for r in (mia, tom):
        s = series[r.name]
        s = s[(s.index >= r.buy_date) & (s.index <= r.sell_date)]
        frames.append(pd.DataFrame({"Date": s.index, "Value": r.amount * s.values / r.buy_price, "Investor": r.name}))
    chart_df = pd.concat(frames)
    chart = (
        alt.Chart(chart_df)
        .mark_line(strokeWidth=2.5)
        .encode(
            x=alt.X("Date:T", title=None),
            y=alt.Y("Value:Q", title="Value of the investment (€)", scale=alt.Scale(zero=False)),
            color=alt.Color("Investor:N", scale=alt.Scale(domain=["Mia", "Tom"], range=[MIA_COLOR, TOM_COLOR]),
                            legend=alt.Legend(orient="top", title=None)),
            tooltip=[alt.Tooltip("Investor:N"), alt.Tooltip("Date:T", format="%d.%m.%Y"),
                     alt.Tooltip("Value:Q", format=",.2f", title="Value (€)")],
        )
        .properties(height=360)
    )
    start_rule = alt.Chart(pd.DataFrame({"y": [amount]})).mark_rule(strokeDash=[4, 4], color="#888").encode(y="y:Q")
    st.altair_chart(chart + start_rule, width="stretch")

# Verdict
more_money = mia if mia.profit > tom.profit else tom
better_pace = mia if mia.cagr > tom.cagr else tom
if more_money is better_pace:
    verdict = (f"**{more_money.name}** wins on both counts: more profit in euros "
               f"and a higher return per year.")
else:
    verdict = (f"It depends on what *better* means. **{more_money.name}** made more money "
               f"({fmt_eur(more_money.profit)} vs. {fmt_eur(better_pace.profit)}), "
               f"but had {abs(mia.years - tom.years):.1f} years more time. "
               f"Per year, **{better_pace.name}** invested better: "
               f"{fmt_pct(better_pace.cagr)} vs. {fmt_pct(more_money.cagr)} (CAGR). "
               f"To compare investments over different periods, use the annual return.")
st.info(verdict)

# --------------------------------------------------------------------------
# Question 2
# --------------------------------------------------------------------------
st.header("2. What was their annual return (CAGR)?")

left, right = st.columns([1, 1])
with left:
    st.latex(r"\text{CAGR} = \left(\frac{\text{final value}}{\text{amount invested}}\right)^{\frac{1}{\text{years}}} - 1")
    m1, m2 = st.columns(2)
    m1.metric("Mia's CAGR", fmt_pct(mia.cagr))
    m2.metric("Tom's CAGR", fmt_pct(tom.cagr))
    st.markdown(
        f"Mia: $({mia.final_value:,.2f} / {amount:,.0f})^{{1/{mia.years:.2f}}} - 1 = {mia.cagr:.2%}$  \n"
        f"Tom: $({tom.final_value:,.2f} / {amount:,.0f})^{{1/{tom.years:.2f}}} - 1 = {tom.cagr:.2%}$"
    )

with right:
    st.markdown("**Why not just divide by the number of years?**")
    table = pd.DataFrame(
        {
            "Total return": [fmt_pct(r.total_return) for r in (mia, tom)],
            "Years": [f"{r.years:.2f}" for r in (mia, tom)],
            "Total return ÷ years (wrong)": [fmt_pct(r.naive_annual) for r in (mia, tom)],
            "CAGR (correct)": [fmt_pct(r.cagr) for r in (mia, tom)],
        },
        index=["Mia", "Tom"],
    )
    st.table(table)
    st.markdown(
        "Dividing ignores compounding: each year's gain also earns returns in the following years. "
        "The simple division therefore overstates the annual return."
    )

# Same horizon comparison
horizon = max(mia.years, tom.years)
st.markdown(
    f"**Same pace, same time:** growing at their CAGR for {horizon:.1f} years, "
    f"{fmt_eur(amount)} would have become **{fmt_eur(amount * (1 + mia.cagr) ** horizon)}** for Mia "
    f"and **{fmt_eur(amount * (1 + tom.cagr) ** horizon)}** for Tom."
)

# --------------------------------------------------------------------------
# Data and assumptions
# --------------------------------------------------------------------------
with st.expander("Data source and assumptions"):
    st.markdown(
        f"""
- **Source:** {"Yahoo Finance via the Python package `yfinance`" if live else "manually entered prices"}.
  Tickers ending in `.DE` are quotes from the Xetra exchange in euros.
- **Buy price:** closing price on the purchase date, or the next trading day if the exchange was closed.
- **Sell price:** closing price on the settlement date, or the last trading day before it.
- **Not included:** fees, taxes and currency effects. Dividends are only included with *adjusted close*.
- **Years:** calendar days between buying and selling divided by 365.25.
"""
    )
    if live:
        raw = pd.DataFrame(
            {"Buy date": [mia.buy_date.date(), tom.buy_date.date()],
             "Buy price": [mia.buy_price, tom.buy_price],
             "Sell date": [mia.sell_date.date(), tom.sell_date.date()],
             "Sell price": [mia.sell_price, tom.sell_price]},
            index=["Mia", "Tom"],
        )
        st.dataframe(raw.style.format({"Buy price": "{:.2f}", "Sell price": "{:.2f}"}))

st.divider()
st.caption("Built with Python, pandas, yfinance, Altair and Streamlit - the tools you will use this semester.")