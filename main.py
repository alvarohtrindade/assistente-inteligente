# main.py
import streamlit as st
from utils import query_isp_info, process_follow_up_question
import base64
from datetime import datetime

def init_session_state():
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    if 'current_isp_data' not in st.session_state:
        st.session_state.current_isp_data = None

def setup_sidebar():
    with st.sidebar:
        # Título da sidebar
        st.image("assets/logo1.png")
        
        # Menu de Navegação
        st.markdown("### Menu de Navegação")
        
        # Botão Nova Consulta
        if st.button("📋 Nova Consulta"):
            st.session_state.messages = []
            st.session_state.current_isp_data = None
            st.rerun()
        
        # Botão Exportar (apenas se houver mensagens)
        if st.session_state.messages:
            if st.button("💾 Exportar Chat"):
                export_chat()
        
        # Links Úteis
        st.markdown("### 🔗 Links Úteis")
        st.markdown("""
        * [Status da plataforma](https://status.watch.tv.br/uptime?page=1)
        * [FAQ](https://exemplo.com/faq)
        """)
        
        # Informações do Sistema
        st.markdown("### ℹ️ Sistema")
        st.markdown(f"""
        * Versão: 1.0.0
        * Última atualização: {datetime.now().strftime('%d/%m/%Y %H:%M')}
        """)

def export_chat():
    if st.session_state.messages:
        chat_text = "Histórico de Chat - ISP Assistant\n\n"
        chat_text += f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
        if st.session_state.current_isp_data:
            chat_text += f"ISP: {st.session_state.current_isp_data['nome']}\n\n"
        
        for msg in st.session_state.messages:
            role = "👤 Usuário" if msg["role"] == "user" else "🤖 Assistente"
            chat_text += f"{role}:\n{msg['content']}\n\n"
        
        b64 = base64.b64encode(chat_text.encode()).decode()
        filename = f"chat_historico_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
        st.sidebar.markdown(
            f'<a href="data:text/plain;base64,{b64}" download="{filename}" style="display: inline-block; padding: 0.5rem 1rem; background-color: #1E3D59; color: white; text-decoration: none; border-radius: 5px;">📥 Download Histórico</a>',
            unsafe_allow_html=True
        )

def display_metrics(isp_data):
    total_tickets_contratados = sum(produto['tickets_contratados'] for produto in isp_data['produtos'])
    total_tickets_metodo = sum(produto['tickets_metodo'] for produto in isp_data['produtos'])
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Status", isp_data['status'])
    with col2:
        st.metric("Tickets Faturados", f"{total_tickets_metodo:,}")
    with col3:
        st.metric("Faturamento Total", isp_data['total_faturamento'])

def main():
    # Configuração inicial
    st.set_page_config(
        page_title="Assistente Comercial Watch",
        page_icon="⚡️",
        #layout="wide",
        initial_sidebar_state="expanded"
    )
    
    init_session_state()
    setup_sidebar()
    
    # Container principal
    st.title("Assistente Comercial ISP 🎯")
    st.write("Digite o CNPJ (sem pontos) ou Razão Social do ISP para começar.")
    
    # Área de busca
    col1, col2 = st.columns([3, 1])
    with col1:
        identifier = st.text_input(
            "Buscar ISP",
            placeholder="Digite CNPJ ou Razão Social",
            key="search_input"
        )
    with col2:
        search_button = st.button("🔍 Consultar", key="search_button")
    
    # Processamento da busca
    if search_button and identifier:
        with st.spinner('Consultando informações...'):
            data, response = query_isp_info(identifier)
            if data:
                st.session_state.current_isp_data = data
                st.session_state.messages = []
                st.session_state.messages.append({"role": "assistant", "content": response})
            else:
                st.error(response)
    
    # Exibição dos resultados e chat
    if st.session_state.current_isp_data:
        st.markdown("---")
        display_metrics(st.session_state.current_isp_data)
        
        # Área de chat
        st.markdown("### 💬 Chat")
        
        # Exibir mensagens
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        
        # Input para novas perguntas
        question = st.chat_input("Faça uma pergunta sobre o ISP...")
        
        if question:
            st.chat_message("user").markdown(question)
            st.session_state.messages.append({"role": "user", "content": question})
            
            with st.spinner('Processando pergunta...'):
                response = process_follow_up_question(
                    question,
                    st.session_state.current_isp_data
                )
                st.chat_message("assistant").markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})

if __name__ == "__main__":
    main()