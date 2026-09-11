
import streamlit as st
import pandas as pd
import plotly.express as px
from snowflake.snowpark.context import get_active_session
import json

session = get_active_session()

st.set_page_config(
    page_title="Retail Sales Insights Copilot",
    layout="wide"
)

st.title("Retail Sales Insights Copilot")
st.write(
    "Explore retail performance using interactive analytics and AI-powered insights."
)

# df = session.sql("""
#     SELECT CURRENT_DATABASE() AS DATABASE_NAME,
#            CURRENT_SCHEMA() AS SCHEMA_NAME,
#            CURRENT_WAREHOUSE() AS WAREHOUSE_NAME,
#            CURRENT_ROLE() AS ROLE_NAME
# """).to_pandas()


# -------------------------------------------------
# SIDEBAR FILTERS
# -------------------------------------------------

st.sidebar.header("🔍 Filters")

# Get available regions
regions = session.sql(""" SELECT DISTINCT REGION
                          FROM RETAIL_TABLE
                          ORDER BY REGION """
                     ).to_pandas()["REGION"].tolist()

# Get available categories
categories = session.sql(""" SELECT DISTINCT CATEGORY
                             FROM RETAIL_TABLE
                             ORDER BY CATEGORY """
                        ).to_pandas()["CATEGORY"].tolist()

# Get date range
date_range = session.sql(""" SELECT MIN(ORDER_DATE) AS MIN_DATE,
                                    MAX(ORDER_DATE) AS MAX_DATE
                             FROM RETAIL_TABLE"""
                        ).to_pandas()

min_date = date_range.iloc[0]["MIN_DATE"]
max_date = date_range.iloc[0]["MAX_DATE"]

# Region filter
selected_regions = st.sidebar.multiselect(
    "Select Region",
    regions,
    default=regions
)

# Category filter
selected_categories = st.sidebar.multiselect(
    "Select Category",
    categories,
    default=categories
)

# Date filter
selected_dates = st.sidebar.date_input(
    "Select Order Date Range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date
)


region_filter = "', '".join(selected_regions)
category_filter = "', '".join(selected_categories)

start_date = selected_dates[0]
end_date = selected_dates[1]

where_condition = f"""
    REGION IN ('{region_filter}')
    AND CATEGORY IN ('{category_filter}')
    AND ORDER_DATE BETWEEN '{start_date}' AND '{end_date}'
"""


# kpi query

kpi_query = f""" SELECT SUM(REVENUE) AS TOTAL_REVENUE,
                        AVG(DISCOUNT) AS AVG_DISCOUNT
                 FROM RETAIL_SALES_VIEW
                 WHERE {where_condition}"""

kpi_df = session.sql(kpi_query).to_pandas()

total_revenue = kpi_df.iloc[0]["TOTAL_REVENUE"]
avg_discount = kpi_df.iloc[0]["AVG_DISCOUNT"]

# Handle NULL values
if total_revenue is None:
    total_revenue = 0

if avg_discount is None:
    avg_discount = 0

top_category_query = f""" SELECT CATEGORY,
                                SUM(REVENUE) AS CATEGORY_REVENUE
                          FROM RETAIL_SALES_VIEW
                          WHERE {where_condition}
                          GROUP BY CATEGORY
                          ORDER BY CATEGORY_REVENUE DESC
                          LIMIT 1 """

top_category_df = session.sql(top_category_query).to_pandas()

if top_category_df.empty:
    top_category = "No Data"
else:
    top_category = top_category_df.iloc[0]["CATEGORY"]


# -------------------------------------------------
# KPI TILES
# -------------------------------------------------

st.subheader("Key Performance Indicators")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "Total Revenue",
        f"${total_revenue:,.2f}"
    )

with col2:
    st.metric(
        "Average Discount",
        f"{avg_discount * 100:.2f}%"
    )

with col3:
    st.metric(
        "Top Category by Revenue",
        top_category
    )


# CORTEX AGENT CHAT


st.divider()

st.subheader("🤖 Retail Sales Chat")

st.write(
    "Ask questions about revenue, regions, categories, "
    "discounts, dates, cities, or retail policies."
)


if "messages" not in st.session_state:
    st.session_state.messages = []


for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])



prompt = st.chat_input(
    "Ask a question about retail sales or policies..."
)


if prompt:
    st.session_state.messages.append(
        {
            "role": "user",
            "content": prompt
        }
    )

    with st.chat_message("user"):
        st.write(prompt)


    request_body = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ]
    }


    # Convert Python dictionary → JSON
    request_json = json.dumps(request_body)
    
    # Prevent breaking Snowflake $$ string
    request_json = request_json.replace("$$", "")


    try:

        result = session.sql(f"""
            SELECT SNOWFLAKE.CORTEX.DATA_AGENT_RUN(
                'RETAIL_SALES_DB1.INGESTION.RETAIL_SALES_COPILOT_AGENT',
                $${request_json}$$
            ) AS RESPONSE
        """).collect()


        agent_response = result[0]["RESPONSE"]


        # Convert JSON string → Python dictionary if needed
        if isinstance(agent_response, str):
            agent_response = json.loads(agent_response)



        response = ""
        for item in agent_response.get("content", []):

            if item.get("type") == "text":
                response += item.get(
                    "text",
                    ""
                )
                
        if not response:
            response = (
                "The Cortex Agent completed the request, "
                "but no final answer was returned."
            )


    except Exception as e:
        response = (
            "The Cortex Agent could not answer your question.\n\n"
            f"Error: {str(e)}"
        )


    with st.chat_message("assistant"):
        st.markdown(response)


    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": response
        }
    )