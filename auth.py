import streamlit as st
from config import ADMIN_PASSWORD


def is_admin() -> bool:
    return st.session_state.get("is_admin", False)


def hide_streamlit_ui() -> None:
    """Hide Streamlit branding and the Manage App widget for non-admin users."""
    if not is_admin():
        st.markdown(
            """
            <style>
            /* Top-right toolbar (hamburger menu) */
            [data-testid="stToolbar"]      { display: none !important; }
            /* Deploy / Manage App button */
            [data-testid="stDeployButton"] { display: none !important; }
            .stDeployButton                { display: none !important; }
            /* Bottom-right status / manage widget */
            [data-testid="stStatusWidget"] { display: none !important; }
            /* Footer (Made with Streamlit + GitHub logo) */
            footer                         { visibility: hidden !important; }
            </style>
            """,
            unsafe_allow_html=True,
        )


def login_form():
    with st.sidebar.expander("Accés administrador", expanded=False):
        pwd = st.text_input("Contrasenya", type="password", key="admin_pwd_input")
        if st.button("Entrar", key="admin_login_btn"):
            if pwd == ADMIN_PASSWORD:
                st.session_state["is_admin"] = True
                st.rerun()
            else:
                st.error("Contrasenya incorrecta")

    if is_admin():
        st.sidebar.success("Sessió d'administrador activa")
        if st.sidebar.button("Sortir"):
            st.session_state["is_admin"] = False
            st.rerun()


def require_admin():
    """Call at the top of any admin-only section."""
    if not is_admin():
        st.warning("Cal accés d'administrador.")
        st.stop()
