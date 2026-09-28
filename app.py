import sys
from pathlib import Path

# Make scripts/ available to existing scraper modules
PROJECT_ROOT = Path(__file__).resolve().parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


import streamlit as st
import pandas as pd

from scripts.scrape_from_url import scrape_from_url
from scripts.read_scraped_comments import read_scraped_comments

st.set_page_config(
    page_title="YouTube Comment Dataset Builder",
    page_icon="▶️",
    layout="wide",
)


st.title("YouTube Comment Dataset Builder")

st.write(
    "Enter a YouTube video URL to extract its comments "
    "and generate a raw comment dataset."
)


# --------------------------------------------------
# INPUT
# --------------------------------------------------

url = st.text_input(
    "YouTube Video URL",
    placeholder="https://www.youtube.com/watch?v=..."
)


# --------------------------------------------------
# SCRAPE BUTTON
# --------------------------------------------------

if st.button(
    "Scrape Comments",
    type="primary",
):

    if not url.strip():
        st.warning("Please enter a YouTube video URL.")

    else:

        try:

            with st.spinner("Scraping comments..."):

                result = scrape_from_url(
                    url.strip()
                )

                comments = read_scraped_comments(
                    result["output_path"]
                )

            st.success(
                f"Successfully collected {len(comments)} comments."
            )

            # Store result for later use
            st.session_state["comments"] = comments
            st.session_state["result"] = result

        except Exception as e:

            st.error(
                f"Scraping failed: {e}"
            )


# --------------------------------------------------
# RESULTS
# --------------------------------------------------

if "comments" in st.session_state:

    comments = st.session_state["comments"]
    result = st.session_state["result"]

    st.divider()

    st.subheader("Video Information")

    col1, col2 = st.columns(2)

    with col1:
        st.write(
            f"**Title:** {result['video_title']}"
        )

    with col2:
        st.write(
            f"**Comments:** {len(comments)}"
        )

    st.subheader("Dataset Preview")

    df = pd.DataFrame(comments)

    st.dataframe(
        df,
        use_container_width=True,
    )

    st.subheader("Download Dataset")

    csv_data = df.to_csv(
        index=False
    ).encode("utf-8-sig")

    json_data = df.to_json(
        orient="records",
        force_ascii=False,
        indent=2,
    ).encode("utf-8")

    col1, col2 = st.columns(2)

    with col1:

        st.download_button(
            "Download CSV",
            data=csv_data,
            file_name="youtube_comments.csv",
            mime="text/csv",
        )

    with col2:

        st.download_button(
            "Download JSON",
            data=json_data,
            file_name="youtube_comments.json",
            mime="application/json",
        )