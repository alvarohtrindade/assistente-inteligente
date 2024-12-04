import os
from langchain.agents import create_sql_agent
from langchain.agents.agent_toolkits import SQLDatabaseToolkit
from langchain.sql_database import SQLDatabase
from langchain.agents.agent_types import AgentType
from langchain_groq import ChatGroq
from langchain.chains import create_sql_query_chain
from langchain.prompts import ChatPromptTemplate
import pandas as pd
from datetime import datetime

class SQLQueryAgent:
    def __init__(self, db_uri):
        self.db = SQLDatabase.from_uri(db_uri)
        self.llm = ChatGroq(
            groq_api_key=os.getenv("GROQ_API_KEY"),
            model_name="mixtral-8x7b-32768",
            temperature=0.1
        )
        self.toolkit = SQLDatabaseToolkit(db=self.db, llm=self.llm)
        self.table_info = self._cache_table_info()
        
    def _cache_table_info(self):
        """Cache das informações das tabelas para uso frequente"""
        return self.db.get_table_info()
    
    def _format_response(self, result_type, data):
        """Formata a resposta baseada no tipo de consulta"""
        if not data:
            return "❌ Nenhum dado encontrado para esta consulta."
            
        if result_type == "historico":
            df = pd.DataFrame(data)
            return f"""
📈 **Histórico de Performance**
* Período analisado: {df['data'].min()} a {df['data'].max()}
* Total de registros: {len(df)}

Resumo por período:
{df.to_markdown()}

💡 Dica: Você pode perguntar sobre um período específico ou produto.
"""
        elif result_type == "lista":
            items = [f"- {item[0]}" for item in data]
            return f"""
📋 **Resultado da Consulta**
Total de itens: {len(items)}

{chr(10).join(items)}

💡 Dica: Você pode pedir mais detalhes sobre qualquer item específico.
"""
        else:
            return f"""
📊 **Resultado da Consulta**
{data}

💡 Dica: Você pode fazer perguntas mais específicas sobre estes dados.
"""

    def query(self, question):
        try:
            # Identifica o tipo de consulta
            query_type = "geral"
            if any(word in question.lower() for word in ["histórico", "evolução", "período"]):
                query_type = "historico"
            elif any(word in question.lower() for word in ["lista", "listar", "mostrar todos"]):
                query_type = "lista"
            
            # Template específico para o tipo de consulta
            prompt = ChatPromptTemplate.from_template("""
            Gere uma query SQL para responder à seguinte pergunta:
            {question}
            
            Considere as seguintes tabelas e relacionamentos:
            {table_info}
            
            Tipo de consulta: {query_type}
            
            Regras:
            1. Use JOINs apropriados
            2. Limite resultados quando apropriado
            3. Ordene de forma relevante
            4. Use funções de agregação quando necessário
            
            Retorne apenas a query SQL, sem explicações.
            """)
            
            # Gera e executa a query
            sql_chain = create_sql_query_chain(self.llm, self.db)
            query = sql_chain.invoke({
                "question": question,
                "table_info": self.table_info,
                "query_type": query_type
            })
            
            # Executa a query
            with self.db.connect() as conn:
                result = conn.execute(query)
                rows = result.fetchall()
                
                return self._format_response(query_type, rows)
                
        except Exception as e:
            return f"""
❌ **Erro na Consulta**
Não foi possível processar sua pergunta devido a: {str(e)}

💡 Sugestões:
1. Seja mais específico na sua pergunta
2. Verifique se os dados solicitados existem
3. Tente reformular a pergunta
"""