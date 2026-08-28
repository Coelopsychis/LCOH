import streamlit as st


def percent_slider(label: str, *, key: str, help: str | None = None) -> None:
    st.slider(
        label,
        min_value=0.0,
        max_value=100.0,
        step=0.1,
        key=key,
        format="%.1f%%",
        help=help,
    )
