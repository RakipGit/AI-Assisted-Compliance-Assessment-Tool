"""Main Streamlit application for the thesis compliance tool."""

import streamlit as st


def main() -> None:
    """Render the initial application page."""
    st.set_page_config(
        page_title="AI-Assisted Compliance Assessment",
        page_icon="🛡️",
        layout="wide",
    )

    st.title("AI-Assisted Compliance Assessment Tool")

    st.write(
        "Proof-of-concept tool for the preliminary assessment of selected "
        "ISO/IEC 27001 and NIS2 security criteria."
    )

    st.info(
        "This tool does not provide ISO certification, legal assurance, "
        "or a complete compliance audit."
    )


if __name__ == "__main__":
    main()