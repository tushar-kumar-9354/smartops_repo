from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.schema import Document
import ollama
from django.conf import settings
import logging
import re
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
import csv
import io
import os
from functools import lru_cache
import time

logger = logging.getLogger(__name__)

class ReportQAEngine:
    """Advanced QA engine for report analysis with RAG for CSV content"""
    
    def __init__(self):
        print("🔍 Initializing ReportQAEngine")
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        print(self.embeddings.model_name)
        self.vector_store = None
        self.csv_vector_store = None
        self.report_metadata = {}
        print("✅ ReportQAEngine initialized with embeddings")

    def _format_insight(self, insight) -> str:
        """Helper function to format insights consistently"""
        try:
            formatted = f"- {insight.key}: {insight.value:.2f} {insight.text}" if insight.value else f"- {insight.key}: {insight.text}"
            print(f"📝 Formatted insight: {formatted}")
            return formatted
        except Exception as e:
            print(f"⚠️ Error formatting insight: {e}")
            return f"- {insight.key}: [Error formatting insight]"

    def build_comprehensive_document(self, report) -> str:
        """Create a comprehensive document text from a report with rich metadata"""
        print(f"📄 Building comprehensive document for report: {report.title} (ID: {report.id})")
        start_time = time.time()
        text_parts = []
        
        # Validate report object
        if not hasattr(report, 'title') or not hasattr(report, 'created_at'):
            print("❌ Invalid report object: missing required attributes")
            logger.error(f"Invalid report object: {report}")
            return ""

        # Basic report info
        text_parts.append(f"REPORT TITLE: {report.title}")
        text_parts.append(f"CREATED DATE: {report.created_at.date()}")
        text_parts.append(f"LAST UPDATED: {report.updated_at.date() if report.updated_at else report.created_at.date()}")
        text_parts.append(f"SOURCE TYPE: {report.source_type}")
        print(f"📋 Added basic report info: {report.title}")
        
        if report.summary:
            text_parts.append(f"SUMMARY: {report.summary}")
            print("📜 Added report summary")
        
        # Add insights with proper formatting
        try:
            insights = report.insights.all()
            print(f"🔎 Found {len(insights)} insights for report")
            if insights:
                text_parts.append("KEY INSIGHTS:")
                for insight in insights:
                    text_parts.append(self._format_insight(insight))
        except Exception as e:
            print(f"⚠️ Error processing insights: {e}")
            logger.warning(f"Error processing insights for report {report.id}: {e}")
        
        # Add sample data stats if available
        data_stats = self._extract_data_statistics(report)
        if data_stats:
            text_parts.append("DATA CHARACTERISTICS:")
            text_parts.append(data_stats)
            print("📊 Added data statistics")
        
        # Add temporal context if relevant
        temporal_info = self._extract_temporal_context(report)
        if temporal_info:
            text_parts.append("TEMPORAL CONTEXT:")
            text_parts.append(temporal_info)
            print("⏰ Added temporal context")
        
        result = "\n".join(text_parts)
        print(f"✅ Built document in {time.time() - start_time:.2f}s, length: {len(result)} characters")
        return result
    
    def _extract_csv_content_for_rag(self, report) -> List[Tuple[str, Dict]]:
        """
        Extract content from CSV files for RAG processing
        Returns list of (text, metadata) tuples
        """
        print(f"📂 Extracting CSV content for report: {report.title} (ID: {report.id})")
        start_time = time.time()
        csv_docs = []
        
        try:
            if not report.csv_file:
                print("⚠️ No CSV file found for report")
                return csv_docs
                
            print(f"📖 Reading CSV file: {report.csv_file.path}")
            df = pd.read_csv(report.csv_file.path)
            print(f"📊 CSV loaded: {df.shape[0]} rows, {df.shape[1]} columns")
            
            # Create document for column descriptions
            columns_metadata = {
                "report_id": report.id,
                "title": report.title,
                "type": "csv_metadata",
                "content_type": "column_descriptions"
            }
            
            columns_text = f"CSV FILE: {os.path.basename(report.csv_file.name)}\n"
            columns_text += f"COLUMNS in {report.title}:\n"
            
            for col in df.columns:
                col_dtype = str(df[col].dtype)
                unique_count = df[col].nunique()
                null_count = df[col].isnull().sum()
                columns_text += f"- {col}: {col_dtype} type, {unique_count} unique values, {null_count} missing values\n"
                
                if pd.api.types.is_numeric_dtype(df[col]):
                    columns_text += f"  Stats: min={df[col].min():.2f}, max={df[col].max():.2f}, mean={df[col].mean():.2f}\n"
            
            csv_docs.append((columns_text, columns_metadata))
            print("📋 Added column descriptions to CSV docs")
            
            # Create sample data documents (first 20 rows or less if dataset is smaller)
            sample_metadata = {
                "report_id": report.id,
                "title": report.title,
                "type": "csv_data",
                "content_type": "sample_data"
            }
            
            sample_text = f"SAMPLE DATA from {report.title} (first {min(20, len(df))} rows):\n"
            sample_df = df.head(20)
            
            for idx, row in sample_df.iterrows():
                sample_text += f"Row {idx}: {dict(row)}\n"
            
            csv_docs.append((sample_text, sample_metadata))
            print(f"📈 Added sample data for {min(20, len(df))} rows")
            
            # Create documents for unique values in categorical columns
            categorical_cols = df.select_dtypes(include=['object']).columns.tolist()
            print(f"🔍 Found {len(categorical_cols)} categorical columns")
            for col in categorical_cols[:5]:  # Limit to first 5
                unique_metadata = {
                    "report_id": report.id,
                    "title": report.title,
                    "type": "csv_metadata",
                    "content_type": "unique_values",
                    "column": col
                }
                
                unique_values = df[col].dropna().unique()[:10]
                unique_text = f"UNIQUE VALUES in column '{col}' of {report.title}:\n"
                unique_text += ", ".join(map(str, unique_values))
                
                csv_docs.append((unique_text, unique_metadata))
                print(f"📝 Added unique values for column: {col}")
            
        except Exception as e:
            print(f"❌ Error extracting CSV content: {e}")
            logger.warning(f"Could not extract CSV content for RAG: {e}")
        
        print(f"✅ Extracted {len(csv_docs)} CSV documents in {time.time() - start_time:.2f}s")
        return csv_docs
    
    @lru_cache(maxsize=1)
    def build_csv_retriever(self):
        """
        Build a separate retriever for CSV content across all reports
        """
        print("🛠️ Building CSV retriever")
        start_time = time.time()
        from .models import Report
        
        csv_docs = []
        csv_metadatas = []
        
        reports = Report.objects.filter(csv_file__isnull=False)
        print(f"📚 Found {reports.count()} reports with CSV files")
        
        for report in reports:
            print(f"🔄 Processing CSV for report: {report.title}")
            csv_content = self._extract_csv_content_for_rag(report)
            
            for text, metadata in csv_content:
                csv_docs.append(text)
                csv_metadatas.append(metadata)
        
        if not csv_docs:
            print("⚠️ No CSV documents available")
            return None
        
        try:
            self.csv_vector_store = FAISS.from_texts(csv_docs, self.embeddings, metadatas=csv_metadatas)
            print(f"✅ CSV vector store built with {len(csv_docs)} documents in {time.time() - start_time:.2f}s")
            return self.csv_vector_store
        except Exception as e:
            print(f"❌ Error building CSV retriever: {e}")
            logger.error(f"Error building CSV retriever: {e}")
            return None
    
    def _extract_data_statistics(self, report) -> Optional[str]:
        """Extract comprehensive statistics from report data"""
        print(f"📊 Extracting data statistics for report: {report.title}")
        start_time = time.time()
        try:
            if not report.csv_file:
                print("⚠️ No CSV file for statistics extraction")
                return None
                
            df = pd.read_csv(report.csv_file.path)
            print(f"📖 Loaded CSV: {df.shape[0]} rows, {df.shape[1]} columns")
            stats_parts = []
            
            stats_parts.append(f"Dataset shape: {df.shape[0]} rows, {df.shape[1]} columns")
            stats_parts.append(f"Columns: {', '.join(df.columns.tolist())}")
            
            dtypes = df.dtypes.value_counts().to_dict()
            stats_parts.append(f"Data types: {', '.join([f'{count} {str(dtype)}' for dtype, count in dtypes.items()])}")
            print(f"📋 Added dataset info and data types")
            
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            if numeric_cols:
                stats_parts.append("NUMERIC COLUMNS STATISTICS:")
                for col in numeric_cols[:5]:
                    stats = df[col].describe()
                    stats_parts.append(
                        f"{col}: mean={stats['mean']:.2f}, min={stats['min']:.2f}, "
                        f"max={stats['max']:.2f}, std={stats['std']:.2f}"
                    )
                print(f"📈 Added stats for {len(numeric_cols[:5])} numeric columns")
            
            categorical_cols = df.select_dtypes(include=['object']).columns.tolist()
            if categorical_cols:
                stats_parts.append("CATEGORICAL COLUMNS INFO:")
                for col in categorical_cols[:3]:
                    unique_count = df[col].nunique()
                    sample_values = df[col].dropna().unique()[:3]
                    stats_parts.append(
                        f"{col}: {unique_count} unique values, sample: {', '.join(map(str, sample_values))}"
                    )
                print(f"📝 Added info for {len(categorical_cols[:3])} categorical columns")
            
            result = "\n".join(stats_parts)
            print(f"✅ Extracted statistics in {time.time() - start_time:.2f}s")
            return result
            
        except Exception as e:
            print(f"❌ Error extracting data statistics: {e}")
            logger.warning(f"Could not extract data statistics: {e}")
            return None
    
    def _extract_temporal_context(self, report) -> Optional[str]:
        """Extract temporal context from report metadata"""
        print(f"⏰ Extracting temporal context for report: {report.title}")
        start_time = time.time()
        try:
            context_parts = []
            title = report.title.lower()
            current_year = datetime.now().year
            
            year_match = re.search(r'\b(20\d{2})\b', title)
            if year_match:
                year = int(year_match.group(1))
                context_parts.append(f"Reference year: {year}")
                if year == current_year:
                    context_parts.append("This report is from the current year")
                elif year == current_year - 1:
                    context_parts.append("This report is from last year")
                print(f"📅 Found year reference: {year}")
            
            quarter_match = re.search(r'\bq([1-4])\b', title)
            if quarter_match:
                context_parts.append(f"Quarter: Q{quarter_match.group(1)}")
                print(f"📅 Found quarter reference: Q{quarter_match.group(1)}")
            
            months = ['january', 'february', 'march', 'april', 'may', 'june', 
                     'july', 'august', 'september', 'october', 'november', 'december']
            for month in months:
                if month in title:
                    context_parts.append(f"Month: {month.capitalize()}")
                    print(f"📅 Found month reference: {month.capitalize()}")
                    break
            
            result = "\n".join(context_parts) if context_parts else None
            print(f"✅ Extracted temporal context in {time.time() - start_time:.2f}s: {result}")
            return result
            
        except Exception as e:
            print(f"❌ Error extracting temporal context: {e}")
            logger.warning(f"Could not extract temporal context: {e}")
            return None
    
    @lru_cache(maxsize=1)
    def build_retriever(self):
        """
        Build an advanced retriever from all reports with comprehensive metadata
        """
        print("🛠️ Building main retriever")
        start_time = time.time()
        from .models import Report
        
        docs = []
        metadatas = []
        
        reports = Report.objects.all().order_by('-created_at')
        print(f"📚 Found {reports.count()} reports")
        
        for report in reports:
            doc_text = self.build_comprehensive_document(report)
            if doc_text:
                docs.append(doc_text)
                metadatas.append({
                    "report_id": report.id, 
                    "title": report.title, 
                    "date": str(report.created_at.date()),
                    "source_type": report.source_type,
                    "has_insights": report.insights.exists(),
                    "has_csv": report.csv_file is not None,
                    "source": "report"
                })
                print(f"📄 Added document for report: {report.title}")
        
        if not docs:
            docs = ["No reports available yet. Please upload some data first."]
            metadatas = [{
                "report_id": 0, 
                "title": "No Reports", 
                "source": "system",
                "has_insights": False,
                "has_csv": False
            }]
            print("⚠️ No reports available, using default document")
        
        try:
            self.vector_store = FAISS.from_texts(docs, self.embeddings, metadatas=metadatas)
            self.report_metadata = {meta["report_id"]: meta for meta in metadatas}
            self.build_csv_retriever()
            print(f"✅ Main retriever built with {len(docs)} documents in {time.time() - start_time:.2f}s")
            return self.vector_store
        except Exception as e:
            print(f"❌ Error building retriever: {e}")
            logger.error(f"Error building retriever: {e}")
            return None
    
    def _classify_query_type(self, query: str) -> Dict[str, Any]:
        """Classify the query type to determine appropriate response strategy"""
        print(f"🔍 Classifying query: {query}")
        start_time = time.time()
        query_lower = query.lower()
        
        if not query or not isinstance(query, str):
            print("❌ Invalid query: empty or not a string")
            return {"type": "invalid", "error": "Query must be a non-empty string"}
        
        # CSV content queries
        csv_patterns = [
            r'in\s+(\w+\.csv)',
            r'csv\s+file\s+(\w+)',
            r'column\s+(\w+)',
            r'what\s+is\s+(\w+)\s+in',
            r'meaning\s+of\s+(\w+)',
            r'data\s+in\s+(\w+)',
            r'values\s+in\s+(\w+)'
        ]
        
        for pattern in csv_patterns:
            match = re.search(pattern, query_lower)
            if match:
                csv_file = match.group(1) if match.group(1) else None
                print(f"✅ Classified as csv_content query, file: {csv_file}")
                return {"type": "csv_content", "csv_file": csv_file}
        
        # Count queries
        if re.search(r'how many|number of|count of|total reports', query_lower):
            print("✅ Classified as count query")
            return {"type": "count", "target": "reports"}
        
        # List queries
        if re.search(r'list|show me|what are|which reports', query_lower):
            if re.search(r'alphabetically|alphabetical', query_lower):
                print("✅ Classified as list query (alphabetical)")
                return {"type": "list", "order": "alphabetical"}
            if re.search(r'recent|latest|newest', query_lower):
                print("✅ Classified as list query (recent)")
                return {"type": "list", "order": "recent"}
            print("✅ Classified as list query (default)")
            return {"type": "list", "order": "default"}
        
        # Specific report queries
        report_match = re.search(r'report\s+(?:called|named|titled)?["\']?([^"\']+)["\']?', query_lower)
        if report_match:
            print(f"✅ Classified as specific_report query, name: {report_match.group(1)}")
            return {"type": "specific_report", "report_name": report_match.group(1)}
        
        # Insight queries
        if re.search(r'insight|finding|analysis|trend|pattern', query_lower):
            print("✅ Classified as insight query")
            return {"type": "insight"}
        
        # Data queries
        if re.search(r'data|statistic|metric|value|number', query_lower):
            print("✅ Classified as data query")
            return {"type": "data"}
        
        # Temporal queries
        if re.search(r'year|month|quarter|date|when|recent|old', query_lower):
            print("✅ Classified as temporal query")
            return {"type": "temporal"}
        
        # Default to general query
        print("✅ Classified as general query")
        print(f"✅ Query classification completed in {time.time() - start_time:.2f}s")
        return {"type": "general"}
    
    def _handle_csv_content_query(self, query: str) -> str:
        """
        Handle queries about specific content inside CSV files using RAG
        """
        print(f"📂 Handling CSV content query: {query}")
        start_time = time.time()
        
        if not self.csv_vector_store:
            print("🔄 Building CSV retriever")
            self.build_csv_retriever()
            
        if not self.csv_vector_store:
            print("❌ No CSV vector store available")
            return "I couldn't access the CSV file data. Please try again later."
        
        retriever = self.csv_vector_store.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 5}
        )
        print("🔍 Retriever configured for similarity search")
        
        relevant_docs = retriever.get_relevant_documents(query)
        print(f"📄 Retrieved {len(relevant_docs)} relevant documents")
        
        if not relevant_docs:
            print("⚠️ No relevant CSV documents found")
            return "I couldn't find information about that specific CSV content in the available reports."
        
        context_parts = ["CSV DATA CONTEXT:"]
        for i, doc in enumerate(relevant_docs):
            metadata = doc.metadata
            context_parts.append(f"\n--- CSV CONTENT {i+1} ---")
            context_parts.append(f"From report: {metadata.get('title', 'Unknown')}")
            context_parts.append(f"Content type: {metadata.get('content_type', 'Unknown')}")
            
            if metadata.get('content_type') == 'column_descriptions':
                context_parts.append("This describes the columns and their characteristics:")
            elif metadata.get('content_type') == 'sample_data':
                context_parts.append("This shows sample data from the CSV:")
            elif metadata.get('content_type') == 'unique_values':
                context_parts.append(f"This shows unique values from column '{metadata.get('column', 'Unknown')}':")
            
            context_parts.append(f"Content:\n{doc.page_content}")
            print(f"📋 Added document {i+1}: {metadata.get('title', 'Unknown')}")
        
        context = "\n".join(context_parts)
        print("📝 Context prepared for CSV query")
        
        prompt = f"""You are a data analysis expert. Use the following CSV file information to answer the user's question.

        {context}

        USER QUESTION: {query}

        Please provide a detailed explanation based on the CSV data. If the question is about a specific column:
        - Explain what the column represents
        - Describe the type of data it contains
        - Mention any statistics or patterns visible in the data
        - Provide examples of values if available

        If you cannot find the specific information, be honest about it.

        DETAILED ANSWER:"""
        print("🧩 Generated CSV prompt")
        
        try:
            response = ollama.chat(
                model="qwen:0.5b",
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.1}
            )
            answer = response["message"]["content"].strip()
            print("✅ Received response from Mistral model")
            print(answer)
        except Exception as e:
            print(f"❌ Error calling Mistral model: {e}")
            logger.error(f"Error calling Mistral for CSV query: {e}")
            return "Error processing CSV query with Mistral model."
        
        sources = list(set([doc.metadata.get('title', 'Unknown') for doc in relevant_docs]))
        if sources:
            answer += f"\n\nBased on data from: {', '.join(sources)}"
            print(f"📜 Added sources: {sources}")
        
        print(f"✅ CSV query handled in {time.time() - start_time:.2f}s")
        print(answer)
        return answer
        
    
    def _generate_count_response(self, query: str, relevant_docs: List[Document]) -> str:
        """Generate response for count queries"""
        print(f"🔢 Handling count query: {query}")
        start_time = time.time()
        from .models import Report
        
        total_reports = Report.objects.count()
        print(f"📊 Total reports: {total_reports}")
        
        if "insight" in query.lower():
            from .models import ReportInsight
            insight_count = ReportInsight.objects.count()
            print(f"📈 Insight count: {insight_count}")
            return f"There are {insight_count} insights across all reports."
        
        if "recent" in query.lower() or "last" in query.lower():
            recent_count = Report.objects.filter(
                created_at__gte=datetime.now() - timedelta(days=30)
            ).count()
            print(f"📅 Recent reports (last 30 days): {recent_count}")
            return f"There are {recent_count} reports created in the last 30 days out of {total_reports} total reports."
        
        print(f"✅ Count query handled in {time.time() - start_time:.2f}s")
        return f"There are {total_reports} reports in the system."
    
    def _generate_list_response(self, query: str, relevant_docs: List[Document]) -> str:
        """Generate response for list queries"""
        print(f"📋 Handling list query: {query}")
        start_time = time.time()
        from .models import Report
        
        reports = Report.objects.all()
        print(f"📚 Found {reports.count()} reports")
        
        if "alphabetically" in query.lower() or "alphabetical" in query.lower():
            reports = reports.order_by('title')
            response = "Reports in alphabetical order:\n"
            print("🔤 Sorting reports alphabetically")
        elif "recent" in query.lower() or "latest" in query.lower():
            reports = reports.order_by('-created_at')
            response = "Most recent reports:\n"
            print("📅 Sorting reports by recent")
        else:
            reports = reports.order_by('-created_at')
            response = "Available reports:\n"
            print("📅 Using default sorting (recent)")
        
        for i, report in enumerate(reports[:10], 1):
            response += f"{i}. {report.title} (created: {report.created_at.date()})"
            if report.insights.exists():
                response += f" - {report.insights.count()} insights"
            response += "\n"
            print(f"📝 Added report {i}: {report.title}")
        
        if reports.count() > 10:
            response += f"\n... and {reports.count() - 10} more reports."
            print(f"📊 Noted {reports.count() - 10} additional reports")
        
        print(f"✅ List query handled in {time.time() - start_time:.2f}s")
        return response
    
    def answer_query(self, query: str) -> str:
        """
        Answer a query using intelligent report analysis with enhanced logic
        """
        print(f"❓ Processing query: {query}")
        start_time = time.time()
        try:
            query_type = self._classify_query_type(query)
            print(f"📋 Query type: {query_type}")
            
            if query_type.get("type") == "invalid":
                print("❌ Invalid query detected")
                return "Invalid query: Please provide a non-empty string."
            
            if query_type["type"] == "csv_content":
                return self._handle_csv_content_query(query)
            
            if query_type["type"] == "count":
                return self._generate_count_response(query, [])
            
            if query_type["type"] == "list":
                return self._generate_list_response(query, [])
            
            if not self.vector_store:
                print("🔄 Building main retriever")
                self.build_retriever()
            
            if not self.vector_store:
                print("❌ No vector store available")
                return "Sorry, I couldn't access the report data. Please try again later."
            
            retriever = self.vector_store.as_retriever(
                search_type="mmr", 
                search_kwargs={
                    "k": 7, 
                    "fetch_k": 15,
                    "lambda_mult": 0.7
                }
            )
            print("🔍 Retriever configured for MMR search")
            
            relevant_docs = retriever.get_relevant_documents(query)
            print(f"📄 Retrieved {len(relevant_docs)} relevant documents")
            
            if not relevant_docs or (len(relevant_docs) == 1 and relevant_docs[0].metadata.get("report_id") == 0):
                print("⚠️ No relevant documents found")
                return self._handle_no_relevant_docs(query, query_type)
            
            context = self._prepare_enhanced_context(relevant_docs, query_type)
            print("📝 Context prepared")
            
            prompt = self._create_intelligent_prompt(query, context, query_type)
            print("🧩 Prompt generated")
            print(prompt)
            
            try:
                response = ollama.chat(
                    model="qwen:0.5b",
                    messages=[{"role": "user", "content": prompt}],
                    options={
                        "temperature": 0.2,
                        "top_p": 0.9,
                        "num_ctx": 4096
                    }
                )
                answer = response["message"]["content"].strip()
                print("✅ Received response from Mistral model")
                print(answer)
            except Exception as e:
                print(f"❌ Error calling Mistral model: {e}")
                logger.error(f"Error calling Mistral for query: {e}")
                return "Error processing query with Mistral model."
            
            answer = self._enhance_answer_with_context(answer, relevant_docs, query_type)
            print(f"✅ Query processed in {time.time() - start_time:.2f}s")
            return answer
            
        except Exception as e:
            print(f"❌ Error answering query: {e}")
            logger.error(f"Error answering query '{query}': {e}", exc_info=True)
            return "Sorry, I encountered an error while processing your question. Please try again with a different phrasing."
    
    def _handle_no_relevant_docs(self, query: str, query_type: Dict[str, Any]) -> str:
        """Handle cases where no relevant documents are found"""
        print(f"⚠️ Handling no relevant documents for query: {query}")
        from .models import Report
        
        total_reports = Report.objects.count()
        print(f"📊 Total reports available: {total_reports}")
        
        if query_type["type"] == "specific_report":
            report_name = query_type.get("report_name", "")
            print(f"📄 Specific report not found: {report_name}")
            return (
                f"I couldn't find a report specifically titled '{report_name}'. "
                f"However, there are {total_reports} other reports available. "
                "You might want to try searching with different keywords or ask about "
                "the general content of available reports."
            )
        
        return (
            f"I couldn't find specific information about '{query}' in the available reports. "
            f"There are {total_reports} reports in the system. You might want to try:\n"
            "1. Using different keywords\n"
            "2. Asking about general report content\n"
            "3. Checking if the relevant data has been uploaded"
        )
    
    def _prepare_enhanced_context(self, relevant_docs: List[Document], query_type: Dict[str, Any]) -> str:
        """Prepare enhanced context from relevant documents"""
        print(f"📝 Preparing enhanced context for {len(relevant_docs)} documents")
        start_time = time.time()
        context_parts = ["AVAILABLE REPORTS CONTEXT:"]
        
        for i, doc in enumerate(relevant_docs[:5]):
            metadata = doc.metadata
            context_parts.append(f"\n--- REPORT {i+1}: {metadata.get('title', 'Unknown')} ---")
            context_parts.append(f"Date: {metadata.get('date', 'Unknown')}")
            context_parts.append(f"Source Type: {metadata.get('source_type', 'Unknown')}")
            content_preview = doc.page_content[:500] + "..." if len(doc.page_content) > 500 else doc.page_content
            context_parts.append(f"Content Preview:\n{content_preview}")
            print(f"📄 Added document {i+1}: {metadata.get('title', 'Unknown')}")
        
        if query_type["type"] == "general":
            from .models import Report
            recent_reports = Report.objects.order_by('-created_at')[:3]
            if recent_reports:
                context_parts.append("\n--- MOST RECENT REPORTS ---")
                for report in recent_reports:
                    context_parts.append(f"- {report.title} ({report.created_at.date()})")
                print(f"📅 Added {len(recent_reports)} recent reports")
        
        result = "\n".join(context_parts)
        print(f"✅ Context prepared in {time.time() - start_time:.2f}s")
        return result
    
    def _create_intelligent_prompt(self, query: str, context: str, query_type: Dict[str, Any]) -> str:
        """Create an intelligent prompt based on query type"""
        print(f"🧩 Creating intelligent prompt for query: {query}")
        start_time = time.time()
        
        base_instructions = """
        You are an advanced report analysis assistant. Use the provided report context to answer the question accurately and comprehensively.

        Important guidelines:
        1. Be specific and factual - use numbers and dates when available
        2. If you're unsure, say so rather than guessing
        3. Focus on the most relevant information from the reports
        4. Structure your response clearly
        5. Acknowledge limitations when information is incomplete
        """
        
        query_specific_instructions = {
            "specific_report": "Focus specifically on the mentioned report. If it's not found, suggest similar reports.",
            "insight": "Highlight key insights, patterns, and findings from the reports.",
            "data": "Provide specific data points, statistics, and metrics. Include numbers when available.",
            "temporal": "Focus on time-related aspects: dates, periods, trends over time.",
            "general": "Provide a comprehensive overview based on all relevant reports."
        }
        
        instruction = query_specific_instructions.get(query_type["type"], "")
        print(f"📋 Using instruction for query type: {query_type['type']}")
        
        prompt_template = f"""{base_instructions}
        {instruction}

        REPORT CONTEXT:
        {context}

        USER QUESTION: {query}

        Please provide a detailed, accurate response based on the reports. If the information isn't available, be honest about it.

        DETAILED RESPONSE:"""
        
        print(f"✅ Prompt created in {time.time() - start_time:.2f}s")
        return prompt_template
    
    def _enhance_answer_with_context(self, answer: str, relevant_docs: List[Document], query_type: Dict[str, Any]) -> str:
        """Enhance the answer with additional context and formatting"""
        print("📝 Enhancing answer with context")
        start_time = time.time()
        
        if relevant_docs and len(relevant_docs) > 0:
            sources = list(set([
                doc.metadata.get('title', 'Unknown Report') 
                for doc in relevant_docs 
                if doc.metadata.get('report_id', 0) != 0
            ]))
            if sources:
                if len(sources) == 1:
                    answer += f"\n\nSource: {sources[0]}"
                else:
                    answer += f"\n\nSources: {', '.join(sources[:3])}"
                print(f"📜 Added sources: {sources}")
        
        if query_type["type"] == "specific_report":
            report_name = query_type.get("report_name", "")
            if report_name.lower() not in answer.lower():
                answer += "\n\nNote: The specific report mentioned wasn't found in the system."
                print(f"⚠️ Specific report not found in answer: {report_name}")
        
        print(f"✅ Answer enhanced in {time.time() - start_time:.2f}s")
        return answer

# Global instance for easier access
qa_engine = ReportQAEngine()

def answer_query(query):
    """Main function to answer queries using the enhanced QA engine"""
    print(f"🚀 Starting query processing: {query}")
    return qa_engine.answer_query(query)

def get_report_count():
    """Get the total number of reports"""
    print("🔢 Getting report count")
    from .models import Report
    count = Report.objects.count()
    print(f"📊 Report count: {count}")
    return count

def get_recent_reports(limit=5):
    """Get recent reports with their insight counts"""
    print(f"📅 Getting {limit} recent reports")
    from .models import Report
    reports = Report.objects.order_by('-created_at')[:limit]
    print(f"📚 Found {len(reports)} recent reports")
    return reports

def get_insights_summary():
    """Get summary of insights across all reports"""
    print("📈 Getting insights summary")
    from .models import ReportInsight
    total_insights = ReportInsight.objects.count()
    recent_insights = ReportInsight.objects.filter(
        created_at__gte=datetime.now() - timedelta(days=7)
    ).count()
    print(f"recent insights: {recent_insights}")
    print(f"total insights: {total_insights}")
    
    avg_insights = total_insights / get_report_count() if get_report_count() > 0 else 0
    print(f"📊 Average insights per report: {avg_insights:.2f}")
    return {
        "total_insights": total_insights,
        "recent_insights": recent_insights,
        "avg_insights_per_report": avg_insights
    }