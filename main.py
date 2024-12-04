# main.py
import streamlit as st
from utils import query_isp_info, process_follow_up_question, calculate_business_metrics
from sql_agent import SQLQueryAgent
import base64
from datetime import datetime
import os

def init_session_state():
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    if 'current_isp_data' not in st.session_state:
        st.session_state.current_isp_data = None
    if 'sql_agent' not in st.session_state:
        st.session_state.sql_agent = SQLQueryAgent(os.getenv("DATABASE_URL"))

def setup_sidebar():
    with st.sidebar:
        st.image("assets/logo1.png", use_column_width=True)
        st.markdown("""---""")
        st.markdown("### Menu de Navegação")
        
        if st.button("📋 Nova Consulta"):
            st.session_state.messages = []
            st.session_state.current_isp_data = None
            st.rerun()
        
        if st.session_state.messages:
            if st.button("💾 Exportar Chat"):
                export_chat()
        
        st.markdown("### 🔗 Links Úteis")
        st.markdown("""
        * [Watch Brasil Status](https://status.watch.tv.br/incidents)
        * [Manual do usuário](https://exemplo.com/faq)
        * [FAQ](https://exemplo.com/suporte)
        """)
        
        st.markdown("### ℹ️ Sistema")
        st.markdown(f"""
        * Versão: 1.0.0
        * Última atualização: {datetime.now().strftime('%d/%m/%Y %H:%M')}
        """)

def display_metrics(isp_data):
    total_tickets_metodo = sum(produto['tickets_metodo'] for produto in isp_data['produtos'])
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Status", isp_data['status'])
    with col2:
        st.metric("Tickets Faturados", f"{total_tickets_metodo:,}")
    with col3:
        st.metric("Faturamento Total", isp_data['total_faturamento'])

def display_business_metrics(isp_data):
    st.markdown("### 📊 Análise de Performance por Produto")
    
    metrics = calculate_business_metrics(isp_data)
    current_date = datetime.now()
    month_name = current_date.strftime('%B/%Y')
    
    # Visão Geral
    total_faturamento = float(isp_data['total_faturamento'].replace('R$ ', '').replace(',', ''))
    
    st.markdown(f"""
    #### 📈 Visão Geral
    * Faturamento Total: R$ {total_faturamento:,.2f}
    * Mês de Referência: {month_name}
    """)
    
    for produto_nome, produto_metrics in metrics["produtos"].items():
        with st.expander(f"📦 {produto_nome} ({produto_metrics['percentual_receita']:.1f}% da receita)"):
            produto_info = next((p for p in isp_data['produtos'] if p['nome'] == produto_nome), {})
            
            # Detalhes do produto
            st.markdown(f"""
            #### Informações do Produto
            * **Pacote**: {produto_info.get('pacote', 'N/A')}
            * **Método de Contratação**: {produto_info.get('pacote_metodo', 'N/A')}
            * **Valor Unitário**: {produto_info.get('valor_unitario', 'N/A')}
            * **Tickets Contratados**: {produto_info.get('tickets_contratados', 0):,}
            * **Tickets Distribuídos**: {produto_info.get('tickets_distribuidos', 0):,}
            * **Tickets para Faturamento**: {produto_info.get('tickets_metodo', 0):,}
            """)
            
            # Métricas de performance
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric(
                    "Taxa de Utilização",
                    f"{produto_metrics['utilizacao_atual']:.1%}",
                    f"{produto_metrics['potencial_crescimento']:+.1%}",
                    help=f"Benchmark do mercado: {produto_metrics['benchmark_utilizacao']:.1%}\nPotencial de crescimento baseado no benchmark"
                )
            
            with col2:
                receita_potencial = produto_metrics['receita_potencial']
                st.metric(
                    "Oportunidade",
                    f"R$ {receita_potencial:,.2f}",
                    help=f"Receita potencial adicional baseada no benchmark do mercado\nTickets potenciais: {produto_metrics['tickets_potenciais']:,}"
                )
            
            with col3:
                roi = produto_metrics['roi_estimado']
                st.metric(
                    "ROI Estimado",
                    f"{roi:.1f}x" if roi > 0 else "N/A",
                    help="Retorno sobre investimento estimado para atingir o benchmark\nConsiderando custos de ativação"
                )

def display_opportunities(isp_data):
    metrics = calculate_business_metrics(isp_data)
    
    st.markdown("### 💡 Oportunidades Identificadas")
    
    opportunity_found = False
    
    for produto_nome, produto_metrics in metrics["produtos"].items():
        if produto_metrics['potencial_crescimento'] > 0.1:
            opportunity_found = True
            st.info(f"""
            **Oportunidade em {produto_nome}**
            - Potencial de crescimento: {produto_metrics['potencial_crescimento']:.1%}
            - Benchmark de mercado: {produto_metrics['benchmark_utilizacao']:.1%}
            - Impacto estimado: R$ {produto_metrics['potencial_upsell'] * produto_metrics['potencial_crescimento'] * 1000:.2f}
            """)
    
    if not opportunity_found:
        st.success("👏 Parabéns! Os produtos estão com boa performance em relação ao mercado.")

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

def process_question(question, isp_data):
    sql_keywords = ['consulta', 'busca', 'procura', 'encontra', 'mostra', 'lista', 'histórico']
    
    if any(keyword in question.lower() for keyword in sql_keywords):
        return st.session_state.sql_agent.query(question)
    else:
        return process_follow_up_question(question, isp_data)

def main():
    st.set_page_config(
        page_title="IA Watch Comercial",
        page_icon="💡",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    init_session_state()
    setup_sidebar()
    
    st.title("Assistente Inteligente ISP 🎯")
    st.write("Digite o CNPJ (sem pontos) ou Razão Social do ISP para começar.")
    
    # Área de busca
    col1, col2 = st.columns([3, 1])
    with col1:
        identifier = st.text_input(
            label="",
            placeholder="Digite CNPJ ou Razão Social",
            key="search_input",
            label_visibility="collapsed"
        )
    with col2:
        search_button = st.button(
            "🔍 Consultar", 
            key="search_button",
            use_container_width=True
        )
    
    if search_button and identifier:
        with st.spinner('Consultando informações...'):
            data, response = query_isp_info(identifier)
            if data:
                st.session_state.current_isp_data = data
                st.session_state.messages = []
                st.session_state.messages.append({"role": "assistant", "content": response})
            else:
                st.error(response)
    
    if st.session_state.current_isp_data:
        st.markdown("---")
        
        # 1. Métricas principais
        display_metrics(st.session_state.current_isp_data)
        
        # 2. Prontuário
        st.markdown("### 📋 Prontuário")
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        
        st.markdown("---")
        
        # 3. Análise de Performance e Oportunidades
        display_business_metrics(st.session_state.current_isp_data)
        display_opportunities(st.session_state.current_isp_data)
        
        st.markdown("---")
        
        # 4. Área de Chat
        st.markdown("### 💬 Chat")
        
        # Input do chat
        question = st.chat_input("Faça uma pergunta sobre o ISP...")
        
        if question:
            st.chat_message("user").markdown(question)
            st.session_state.messages.append({"role": "user", "content": question})
            
            with st.spinner('Processando pergunta...'):
                response = process_question(
                    question,
                    st.session_state.current_isp_data
                )
                st.chat_message("assistant").markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})

if __name__ == "__main__":
    main()