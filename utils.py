# utils.py
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from langchain_groq import ChatGroq
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import json
from datetime import datetime

load_dotenv()

def get_db_engine():
    DATABASE_URL = os.getenv("DATABASE_URL")
    return create_engine(DATABASE_URL)

def get_llm():
    return ChatGroq(
        groq_api_key=os.getenv("GROQ_API_KEY"),
        model_name="mixtral-8x7b-32768",
        temperature=0.1,
    )

FOLLOW_UP_PROMPT = """
Você é um consultor comercial estratégico especializado no mercado B2B2C de streaming e SVAs (Serviços de Valor Agregado).
Analise os dados do ISP {isp_name} e responda à pergunta considerando:

PERGUNTA DO USUÁRIO: {question}

DADOS DISPONÍVEIS:
{data}

DIRETRIZES DE RESPOSTA:
1. ANÁLISE DE PRODUTO E MERCADO
   - Avalie o mix atual de produtos
   - Identifique oportunidades de expansão
   - Compare tickets contratados vs. utilizados
   - Analise métodos de contratação (Acessos/Ativação)

2. ESTRATÉGIAS DE VENDA
   - UPSELL: Sugira upgrades nos produtos atuais
   - CROSS-SELL: Identifique produtos complementares
   - SELL IN: Estratégias para aumentar adoção de tickets
   - SELL OUT: Táticas para estimular o uso pelos assinantes

3. INSIGHTS DE PERFORMANCE
   - Taxa de utilização dos tickets
   - Tendências de consumo
   - Potencial de crescimento
   - Comparação com benchmarks do mercado

FORMATAÇÃO DA RESPOSTA:
1. Comece com uma análise objetiva do cenário atual
2. Forneça insights específicos baseados nos dados
3. Sugira ações práticas e mensuráveis
4. Use emojis apropriados para melhor visualização
5. Mantenha um tom consultivo e estratégico

EXEMPLOS DE RESPOSTAS:

Para perguntas sobre produtos:
📊 **Análise Atual**
* Mix de produtos: [detalhes]
* Performance: [métricas]

📈 **Oportunidades Identificadas**
* Upsell: [sugestões baseadas em dados]
* Cross-sell: [produtos complementares]

🎯 **Próximos Passos Recomendados**
1. [Ação específica]
2. [Ação específica]

Para perguntas sobre performance:
📊 **Cenário Atual**
* Utilização: [taxas]
* Benchmark: [comparativo]

💡 **Insights**
* [Observação estratégica]
* [Oportunidade identificada]

🎯 **Recomendações**
1. [Ação específica]
2. [Ação específica]

Para perguntas sobre potencial:
📈 **Análise de Mercado**
* Tamanho da base: [números]
* Penetração atual: [percentual]

💰 **Oportunidades**
* Potencial de receita: [projeção]
* Áreas de crescimento: [detalhes]

🎯 **Estratégia Sugerida**
1. [Ação específica]
2. [Ação específica]

SEMPRE TERMINE COM:
💡 Posso ajudar com mais detalhes sobre [sugestão relevante baseada na conversa]?
"""

def format_date(date_str):
    if date_str and date_str != "None":
        try:
            date_obj = datetime.strptime(str(date_str), "%Y-%m-%d")
            return date_obj.strftime("%d/%m/%Y")
        except:
            return date_str
    return "Não disponível"

def query_isp_info(identifier):
    engine = get_db_engine()
    
    query = text("""
        WITH RankedProducts AS (
            SELECT 
                c.Id as sf_id,
                c.CA_CNPJ__c,
                c.Name,
                c.CA_SituacaoFinanceira__c,
                c.ERP__c,
                c.CA_DataUltFaturamento__c,
                m.produto_sf_code,
                m.pacote_id,
                m.pacote_valor_unit,
                SUM(m.valor_total) as valor_total,
                m.isp_vencimento,
                m.isp_sf_status,
                MAX(m.tickets_contratados) as tickets_contratados,
                MAX(m.tickets_distribuidos) as tickets_distribuidos,
                m.pacote_metodo,
                m.tickets_metodo,
                (m.tickets_metodo * m.pacote_valor_unit) as valor_calculado,
                ROW_NUMBER() OVER (PARTITION BY m.produto_sf_code ORDER BY m.isp_vencimento DESC) as rn
            FROM DIM_SF_CONTAS c
            LEFT JOIN COM_MATRIZ_PRECO_V2 m ON c.Id = m.isp_sf_id
            WHERE """ + 
            ("c.CA_CNPJ__c = :identifier" if identifier.isdigit() else "c.Name LIKE :identifier") +
            """
            GROUP BY 
                c.Id,
                c.CA_CNPJ__c,
                c.Name,
                c.CA_SituacaoFinanceira__c,
                c.ERP__c,
                c.CA_DataUltFaturamento__c,
                m.produto_sf_code,
                m.pacote_id,
                m.pacote_valor_unit,
                m.isp_vencimento,
                m.isp_sf_status,
                m.pacote_metodo,
                m.tickets_metodo
        )
        SELECT *
        FROM RankedProducts
        WHERE rn = 1 AND produto_sf_code IS NOT NULL
        ORDER BY produto_sf_code;
    """)
    
    try:
        with engine.connect() as conn:
            params = {"identifier": identifier if identifier.isdigit() else f"%{identifier}%"}
            result = conn.execute(query, params)
            rows = result.fetchall()
            
            if not rows:
                return None, "⚠️ Nenhum ISP encontrado com os dados informados. Por favor, verifique o CNPJ ou Razão Social."
            
            # Dados base do ISP
            base_data = {
                "sf_id": rows[0][0],
                "cnpj": rows[0][1],
                "nome": rows[0][2],
                "situacao_financeira": rows[0][3] or "Não especificado",
                "erp": rows[0][4] or "Não disponível",
                "ultimo_faturamento": format_date(rows[0][5]),
                "vencimento": rows[0][10] or "Não especificado",
                "status": rows[0][11] or "Não especificado"
            }
            
            # Lista de produtos
            produtos = []
            total_faturamento = 0
            
            for row in rows:
                if row[6]:  # Se tem produto
                    valor_total = float(row[9]) if row[9] else 0
                    total_faturamento += valor_total
                    valor_calculado = float(row[16]) if row[16] else 0
                    
                    produtos.append({
                        "nome": row[6],
                        "pacote": row[7],
                        "valor_unitario": f"R$ {row[8]:.2f}" if row[8] else "Não especificado",
                        "valor_total": f"R$ {valor_total:.2f}",
                        "tickets_contratados": row[12] or 0,
                        "tickets_distribuidos": row[13] or 0,
                        "pacote_metodo": row[14] or "Não especificado",
                        "tickets_metodo": row[15] or 0,
                        "valor_calculado": f"R$ {valor_calculado:.2f}"
                    })
            
            data = {**base_data, "produtos": produtos, "total_faturamento": f"R$ {total_faturamento:.2f}"}
            
            # Formato do prontuário
            initial_response = f"""
Aqui está o prontuário do ISP:

1. 📦 **Produtos e Pacotes:**"""
            
            for produto in produtos:
                initial_response += f"""
   * **{produto['nome']}**:
      - Pacote: {produto['pacote']}
      - Método de Contratação: {produto['pacote_metodo']}
      - Valor unitário: {produto['valor_unitario']}
      - Tickets contratados: {produto['tickets_contratados']:,}
      - Tickets distribuídos: {produto['tickets_distribuidos']:,}
      - Tickets para faturamento: {produto['tickets_metodo']:,}
      - Valor faturado: {produto['valor_calculado']}
      - Percentual utilizado: {(produto['tickets_distribuidos']/produto['tickets_contratados']*100):.1f}%"""

            initial_response += f"""

2. 💰 **Financeiro:**
   * Faturamento total: {data['total_faturamento']}
   * Vencimento: {data['vencimento']}

3. 🔄 **Sistema:**
   * ERP integrado: {data['erp']}

**Informações adicionais:**
* Nome do ISP: {data['nome']}
* CNPJ: {data['cnpj']}
* Situação financeira: {data['situacao_financeira']}

Como posso ajudar você? Algumas sugestões:
* Gostaria de saber mais detalhes sobre algum produto específico? 📦
* Quer informações sobre o método de contratação de um produto? 💼
* Posso detalhar melhor os valores de faturamento? 💰
"""
            return data, initial_response
        
    except Exception as e:
        return None, f"❌ Erro ao consultar o banco de dados: {str(e)}"
    
# Função atualizada para processar dados de benchmark
def get_benchmark_data(produto_nome):
    # Aqui você poderia adicionar uma consulta ao banco para buscar dados de benchmark
    benchmarks = {
        "PARAMOUNT+ AVULSO": {
            "media_utilizacao": 0.65,  # 65% de utilização média
            "ticket_medio": 4.80,
            "penetracao_mercado": 0.45  # 45% de penetração média
        },
        "HBO MAX": {
            "media_utilizacao": 0.70,
            "ticket_medio": 19.10,
            "penetracao_mercado": 0.35
        },
        "WATCH LIGHT": {
            "media_utilizacao": 0.75,
            "ticket_medio": 0.30,
            "penetracao_mercado": 0.60
        }
    }
    return benchmarks.get(produto_nome, {})

def calculate_business_metrics(isp_data):
    """Calcula métricas de negócio para enriquecer a análise"""
    metrics = {
        "produtos": {}
    }
    
    for produto in isp_data["produtos"]:
        nome = produto["nome"]
        benchmark = get_benchmark_data(nome)
        
        utilizacao_atual = produto["tickets_distribuidos"] / produto["tickets_contratados"]
        valor_unitario = float(produto["valor_unitario"].replace("R$ ", ""))
        
        metrics["produtos"][nome] = {
            "utilizacao_atual": utilizacao_atual,
            "benchmark_utilizacao": benchmark.get("media_utilizacao", 0),
            "potencial_crescimento": max(0, benchmark.get("media_utilizacao", 0) - utilizacao_atual),
            "ticket_medio_atual": valor_unitario,
            "benchmark_ticket": benchmark.get("ticket_medio", 0),
            "potencial_upsell": benchmark.get("ticket_medio", 0) - valor_unitario
        }
    
    return metrics

def process_follow_up_question(question, isp_data):
    business_metrics = calculate_business_metrics(isp_data)
    enhanced_data = {**isp_data, "business_metrics": business_metrics}
    
    llm = get_llm()
    output_parser = StrOutputParser()
    
    prompt = ChatPromptTemplate.from_template(FOLLOW_UP_PROMPT)
    chain = prompt | llm | output_parser
    
    response = chain.invoke({
        "isp_name": isp_data["nome"],
        "question": question,
        "data": json.dumps(enhanced_data, ensure_ascii=False, indent=2)
    })
    
    return response.strip()