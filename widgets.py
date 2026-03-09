import streamlit as st


def percent_slider(
    label: str,
    key: str,
    help: str | None = None,
) -> float:
    """
    Streamlit Slider für Prozentwerte.

    UI: 0-100 %
    Rückgabewert: 0-1
    """

    percent_value = st.slider(
        label,
        min_value=0,
        max_value=100,
        key=key,
        format="%d %%",   # Anzeige mit %
        help=help,
    )

    return percent_value / 100