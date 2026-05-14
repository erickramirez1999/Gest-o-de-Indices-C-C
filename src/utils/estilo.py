"""CSS LLE Índices — identidade visual aplicada ao Streamlit."""
from __future__ import annotations
import streamlit as st
from src.utils.marca import (
    AZUL_ESCURO, AMARELO, VERDE, AZUL_VIVO, BRANCO,
    CINZA_CLARO, CINZA_MEDIO, BORDA_FINA,
)


def aplicar_css_lle():
    st.markdown(f"""
    <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {{
            --lle-azul: {AZUL_ESCURO};
            --lle-amarelo: {AMARELO};
            --lle-verde: {VERDE};
            --lle-azul-vivo: {AZUL_VIVO};
            --lle-branco: {BRANCO};
            --lle-cinza: {CINZA_CLARO};
            --lle-cinza-medio: {CINZA_MEDIO};
            --lle-borda: {BORDA_FINA};
        }}
        html, body, [class*="css"], [class*="st-"], button, input, select, textarea {{
            font-family: 'Montserrat', Calibri, Arial, sans-serif !important;
        }}
        h1, h2, h3, h4, h5 {{
            color: var(--lle-azul) !important;
            font-weight: 700 !important;
        }}
        .stButton > button[kind="primary"] {{
            background-color: var(--lle-azul) !important;
            color: var(--lle-branco) !important;
            border: none !important;
            font-weight: 600 !important;
            border-radius: 6px !important;
        }}
        .stButton > button[kind="primary"]:hover {{
            background-color: var(--lle-azul-vivo) !important;
        }}
        .stButton > button[kind="secondary"] {{
            border: 1.5px solid var(--lle-azul) !important;
            color: var(--lle-azul) !important;
            font-weight: 600 !important;
            background-color: var(--lle-branco) !important;
        }}
        section[data-testid="stSidebar"] {{
            background-color: var(--lle-azul) !important;
        }}
        section[data-testid="stSidebar"] * {{
            color: var(--lle-branco) !important;
        }}
        section[data-testid="stSidebar"] .stButton > button {{
            background-color: rgba(255,255,255,0.08) !important;
            color: var(--lle-branco) !important;
            border: 1px solid rgba(255,255,255,0.2) !important;
        }}
        section[data-testid="stSidebar"] .stButton > button:hover {{
            background-color: var(--lle-amarelo) !important;
            color: var(--lle-azul) !important;
            border-color: var(--lle-amarelo) !important;
        }}
        [data-testid="stSidebarNav"] {{ display: none !important; }}
        div[data-testid="stMetricValue"] {{
            color: var(--lle-azul) !important;
            font-weight: 700 !important;
        }}
        .stDataFrame thead th {{
            background-color: var(--lle-azul) !important;
            color: var(--lle-branco) !important;
            font-weight: 600 !important;
        }}
        .block-container {{
            padding-top: 2rem !important;
            max-width: 1400px;
        }}
        footer {{ visibility: hidden; }}
        header[data-testid="stHeader"] {{ background: transparent; display: none !important; }}
        button[data-testid="collapsedControl"] {{
            background: var(--lle-azul) !important;
            border: 1px solid var(--lle-amarelo) !important;
            border-radius: 6px !important;
            font-size: 0 !important;
            min-width: 36px !important; min-height: 36px !important;
        }}
        button[data-testid="collapsedControl"]::before {{
            content: "☰" !important;
            font-size: 20px !important;
            color: var(--lle-amarelo) !important;
        }}
        section[data-testid="stFileUploaderDropzone"] {{
            border: 2px dashed var(--lle-azul) !important;
            border-radius: 8px !important;
        }}
        /* FIX: Ícones Material sobrepondo texto dos botões */
        span[data-testid="stIconMaterial"],
        span.material-icons,
        span.material-symbols-outlined,
        span.material-symbols-rounded,
        span[class*="stIconMaterial"] {{
            font-family: 'Material Symbols Outlined', 'Material Symbols Rounded',
                         'Material Icons' !important;
            font-weight: normal !important;
            font-style: normal !important;
            letter-spacing: normal !important;
            text-transform: none !important;
            display: inline-block !important;
            white-space: nowrap !important;
            word-wrap: normal !important;
            direction: ltr !important;
            -webkit-font-smoothing: antialiased !important;
        }}
        @supports not (font-variation-settings: normal) {{
            span[data-testid="stIconMaterial"],
            span.material-icons,
            span.material-symbols-outlined,
            span.material-symbols-rounded {{
                color: transparent !important;
                font-size: 0 !important;
            }}
        }}
        @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0&display=block');
        button[data-testid="collapsedControl"] {{
            background: var(--lle-azul) !important;
            border: 1px solid var(--lle-amarelo) !important;
            border-radius: 6px !important;
            font-size: 0 !important;
            min-width: 36px !important; min-height: 36px !important;
        }}
        button[data-testid="collapsedControl"]::before {{
            content: "☰" !important;
            font-size: 20px !important;
            color: var(--lle-amarelo) !important;
        }}
    </style>
    """, unsafe_allow_html=True)


def card_kpi(titulo: str, valor: str, sublabel: str, cor: str, icone: str = "") -> str:
    return f"""
    <div style="background:#FFF; border-left:5px solid {cor};
                padding:14px 18px; border-radius:8px;
                box-shadow:0 1px 4px rgba(0,0,0,0.08); height:105px;">
        <div style="font-size:12px; color:#666; font-weight:600; margin-bottom:6px;">
            {icone} {titulo}
        </div>
        <div style="font-size:22px; font-weight:800; color:{cor}; line-height:1.1;">
            {valor}
        </div>
        <div style="font-size:11px; color:#999; margin-top:4px;">{sublabel}</div>
    </div>
    """


def badge_variacao(valor: float, positivo_eh_bom: bool = True) -> str:
    if valor is None:
        return ""
    cor = VERDE if (valor >= 0) == positivo_eh_bom else "#DC3545"
    sinal = "▲" if valor >= 0 else "▼"
    return (
        f"<span style='background:{cor}22; color:{cor}; padding:2px 8px; "
        f"border-radius:10px; font-size:12px; font-weight:600;'>"
        f"{sinal} {abs(valor):.2f} pp</span>"
    )
