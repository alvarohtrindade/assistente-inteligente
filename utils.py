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
Você é um consultor comercial especializado no mercado B2B2C de streaming.
Analise os dados da ISP {isp_name} e responda de forma objetiva.

CONTEXTO:
{data}

PERGUNTA: {question}

REGRAS DE RESPOSTA:
1. NUNCA repita informações já apresentadas
2. Use no máximo 2 seções por resposta
3. Foque apenas no que foi perguntado
4. Formate todos os valores monetários com vírgula e duas casas decimais
5. Sugira apenas UMA próxima pergunta relevante

TIPOS DE RESPOSTAS:

Para perguntas técnicas:
📊 **Explicação Técnica**
* [Conceito técnico explicado de forma simples]
* [Exemplo prático usando dados da ISP]
* [Impacto no negócio]

Para análise de produtos:
📈 **Análise de [Nome do Produto]**
* Performance Atual: [métricas principais]
* Comparativo Mercado: [benchmarks relevantes]
* Próximo Passo: [ação específica e mensurável]

Para estratégias:
🎯 **Estratégia para [Objetivo]**
* Foco: [produto/segmento específico]
* Motivo: [dados que justificam]
* Ação: [passo prático e mensurável]

Para análise histórica:
📅 **Evolução [Período]**
* Início: [métricas iniciais]
* Atual: [métricas atuais]
* Tendência: [direção com dados]

NÃO REPITA dados que já aparecem no prontuário ou em perguntas anteriores.
SEMPRE sugira uma próxima pergunta que agregue valor ao contexto atual.
"""

def format_date(date_str):
    if date_str and date_str != "None":
        try:
            date_obj = datetime.strptime(str(date_str), "%Y-%m-%d")
            return date_obj.strftime("%d/%m/%Y")
        except:
            return date_str
    return "Não disponível"

def get_benchmark_data(produto_nome):
    benchmarks = {
        "PARAMOUNT+ AVULSO": {
            "media_utilizacao": 0.65,
            "ticket_medio": 4.80,
            "penetracao_mercado": 0.45,
            "churn_aceitavel": 0.15
        },
        "HBO MAX": {
            "media_utilizacao": 0.70,
            "ticket_medio": 19.10,
            "penetracao_mercado": 0.35,
            "churn_aceitavel": 0.12
        },
        "WATCH LIGHT": {
            "media_utilizacao": 0.75,
            "ticket_medio": 0.30,
            "penetracao_mercado": 0.60,
            "churn_aceitavel": 0.20
        }
    }
    # Valores padrão para produtos não mapeados
    default = {
        "media_utilizacao": 0.60,
        "ticket_medio": 0.0,
        "penetracao_mercado": 0.40,
        "churn_aceitavel": 0.15
    }
    return benchmarks.get(produto_nome, default)

def calculate_business_metrics(isp_data):
    metrics = {
        "produtos": {},
        "total_faturamento": 0,
        "distribuicao_receita": {}
    }
    
    # Calcula faturamento total
    total_faturamento = sum(
        float(p['valor_calculado'].replace('R$ ', '').replace(',', '')) 
        for p in isp_data['produtos']
    )
    metrics['total_faturamento'] = total_faturamento
    
    for produto in isp_data["produtos"]:
        nome = produto["nome"]
        benchmark = get_benchmark_data(nome)
        
        # Cálculos básicos
        valor_unitario = float(produto["valor_unitario"].replace("R$ ", ""))
        valor_produto = float(produto['valor_calculado'].replace('R$ ', '').replace(',', ''))
        utilizacao_atual = produto["tickets_distribuidos"] / produto["tickets_contratados"]
        
        # Métricas avançadas
        potencial_crescimento = max(0, benchmark["media_utilizacao"] - utilizacao_atual)
        tickets_potenciais = int(produto["tickets_contratados"] * potencial_crescimento)
        receita_potencial = tickets_potenciais * valor_unitario
        
        # Cálculo de ROI
        custo_estimado = receita_potencial * 0.3  # 30% é um valor exemplo para custo de ativação
        roi_estimado = (receita_potencial - custo_estimado) / custo_estimado if custo_estimado > 0 else 0
        
        metrics["produtos"][nome] = {
            "utilizacao_atual": utilizacao_atual,
            "benchmark_utilizacao": benchmark["media_utilizacao"],
            "potencial_crescimento": potencial_crescimento,
            "ticket_medio_atual": valor_unitario,
            "benchmark_ticket": benchmark["ticket_medio"],
            "potencial_upsell": benchmark["ticket_medio"] - valor_unitario,
            "percentual_receita": (valor_produto / total_faturamento * 100) if total_faturamento > 0 else 0,
            "receita_potencial": receita_potencial,
            "roi_estimado": roi_estimado,
            "tickets_potenciais": tickets_potenciais
        }
        
        metrics['distribuicao_receita'][nome] = metrics['produtos'][nome]['percentual_receita']
    
    return metrics

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
            
            initial_response = f"""
Aqui está o prontuário do ISP:

💰 **Financeiro:**
   * Faturamento total: {data['total_faturamento']}
   * Vencimento: {data['vencimento']}

🔄 **Sistema:**
   * ERP integrado: {data['erp']}

**Informações adicionais:**
* Nome do ISP: {data['nome']}
* CNPJ: {data['cnpj']}
* Situação financeira: {data['situacao_financeira']}

Como posso ajudar você? Algumas sugestões:
* Gostaria de analisar a performance dos produtos? 📦
* Quer conhecer estratégias de vendas personalizadas? 🎯
* Posso detalhar melhor a situação financeira? 💰
"""
            return data, initial_response
        
    except Exception as e:
        return None, f"❌ Erro ao consultar o banco de dados: {str(e)}"

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