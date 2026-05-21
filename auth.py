import streamlit as st
from config import ADMIN_PASSWORD


def is_admin() -> bool:
    return st.session_state.get("is_admin", False)


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
