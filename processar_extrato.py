#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import csv
import sys
import json
from collections import defaultdict
from datetime import datetime

def parse_float_br(val_str):
    """Converte string de valor no padrão brasileiro (ex: 9.284,75 ou 150,00) para float."""
    try:
        clean_str = val_str.replace('.', '').replace(',', '.')
        return float(clean_str)
    except ValueError:
        return 0.0

def format_float_br(val):
    """Formata valor float de volta para o padrão brasileiro (ex: 150,00 ou 1.250,50)."""
    return f"{val:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.')

def find_initial_balance(file_path):
    """
    Varre o arquivo de extrato buscando a linha de SALDO ANTERIOR mais antiga
    para determinar o saldo inicial do período.
    """
    if not os.path.exists(file_path):
        return 0.0
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        text = f.read()
    
    # Procura por "SALDO ANTERIOR"
    pat = re.compile(r'(\d{2}/\d{2}/\d{4})\s+SALDO ANTERIOR\s+([\d\.,]+)([CD])')
    matches = pat.findall(text)
    if matches:
        try:
            # Ordena por data para garantir que pegamos o primeiro saldo anterior cronologicamente
            matches_sorted = sorted(matches, key=lambda x: datetime.strptime(x[0], '%d/%m/%Y'))
            first_match = matches_sorted[0]
            val = parse_float_br(first_match[1])
            if first_match[2] == 'D':
                val = -val
            return val
        except Exception:
            first_match = matches[0]
            val = parse_float_br(first_match[1])
            if first_match[2] == 'D':
                val = -val
            return val
    return 0.0

def parse_sicoob_statement(file_path):
    """
    Realiza o parse robusto de um arquivo de extrato do Sicoob em formato TXT.
    Lida com form feeds, cabeçalhos de páginas e transações multilinhas.
    """
    if not os.path.exists(file_path):
        print(f"Erro: Arquivo não encontrado em {file_path}")
        return []

    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        text = f.read()

    # Limpar form feeds (\x0c) que aparecem em quebras de página
    text = text.replace('\x0c', '')
    lines = text.split('\n')

    # Regex para identificar o início de uma transação:
    # Grupo 1: Data (DD/MM/AAAA)
    # Grupo 2: Documento (Doc/Pix/Número)
    # Grupo 3: Descrição da transação
    # Grupo 4: Valor (com pontos e vírgula)
    # Grupo 5: Indicador de Débito (D) ou Crédito (C) ou Bloqueado (*)
    tx_header_pat = re.compile(r'^(\d{2}/\d{2}/\d{4})\s+(\S+)\s+(.+?)\s+([\d\.,]+)([CD\*])$')
    saldo_pat = re.compile(r'SALDO DO DIA|SALDO ANTERIOR|SALDO BLOQUEADO')

    transactions = []
    current_tx = None

    for i, line in enumerate(lines):
        line_stripped = line.strip()
        if not line_stripped:
            continue

        # Tenta casar o padrão de início de transação
        m = tx_header_pat.match(line_stripped)
        if m:
            date, doc, desc, val_str, dc = m.groups()
            
            # Se for uma linha de saldo, não é uma movimentação real. Encerra a transação atual.
            if saldo_pat.search(desc) or doc == 'SALDO' or 'SALDO' in desc:
                if current_tx:
                    transactions.append(current_tx)
                    current_tx = None
                continue
                
            # Salva a transação anterior se houver
            if current_tx:
                transactions.append(current_tx)
                
            current_tx = {
                'line_num': i + 1,
                'date': date,
                'doc': doc,
                'description': desc.strip(),
                'value_str': val_str,
                'value': parse_float_br(val_str),
                'dc': dc,
                'details': []
            }
        else:
            # Tratamento de linhas sem cabeçalho (detalhes da transação atual ou delimitadores de página)
            # Se bater em delimitadores de extrato, encerra a transação atual
            if (line_stripped.startswith('RESUMO') or 
                line_stripped.startswith('ENCARGOS') or 
                line_stripped.startswith('OUTRAS INFORMAÇÕES') or 
                'SICOOB' in line_stripped or 
                'COOP.:' in line_stripped or 
                'CONTA:' in line_stripped):
                if current_tx:
                    transactions.append(current_tx)
                    current_tx = None
                continue
                
            if current_tx:
                # O saldo do dia às vezes vem recuado sem data. Ignoramos como transação.
                if 'SALDO DO DIA ===== >' in line_stripped:
                    transactions.append(current_tx)
                    current_tx = None
                    continue
                current_tx['details'].append(line_stripped)

    # Adiciona a última transação caso tenha sobrado
    if current_tx:
        transactions.append(current_tx)

    return transactions

def extract_fields(tx):
    """
    Extrai campos semânticos (Payer/Favorecido, CPF/CNPJ, Comentário) 
    a partir dos detalhes multilinhas da transação.
    """
    desc = tx['description']
    details = tx['details']
    dc = tx['dc']
    
    name = ""
    identifier = ""
    remark = ""
    
    if dc == 'C': # Recebimentos (Crédito)
        if desc == 'PIX RECEBIDO - OUTRA IF':
            if len(details) >= 2:
                name = details[1].strip()
            if len(details) >= 3:
                identifier = details[2].strip()
            if len(details) >= 4:
                remark = " ".join(details[3:]).strip()
        elif desc in ('TRANSF.RECEBIDA - PIX SICOOB', 'CRED.TRANSF.CONTAS INTERCREDIS'):
            # Procura por "REM.: Nome" nos detalhes
            for line in details:
                if line.startswith('REM.:'):
                    name = line.replace('REM.:', '').strip()
            if len(details) >= 3 and not name:
                name = details[2].strip()
            if len(details) >= 4:
                identifier = details[3].strip()
            if len(details) >= 5:
                remark = " ".join(details[4:]).strip()
        elif desc == 'CRÉDITO DEVOLUÇÃO PIX':
            if len(details) >= 2:
                name = details[1].strip()
            if len(details) >= 3:
                identifier = details[2].strip()
        elif desc == 'ESTORNO PIX EMITIDO':
            if len(details) >= 2:
                identifier = details[1].strip()
            if len(details) >= 3:
                remark = " ".join(details[2:]).strip()
        else:
            name = desc
            remark = " ".join(details).strip()
            
    else: # Despesas (Débito)
        if desc == 'PIX EMITIDO OUTRA IF':
            if len(details) >= 2:
                name = details[1].strip()
            if len(details) >= 3:
                remark = " ".join(details[2:]).strip()
        elif desc == 'TRANSF.REALIZADA PIX SICOOB':
            if len(details) >= 1:
                name = details[0].replace('FAV.:', '').strip()
            if len(details) >= 5:
                remark = " ".join(details[4:]).strip()
        elif desc == 'DÉBITO DEVOLUÇÃO PIX':
            if len(details) >= 2:
                identifier = details[1].strip()
        else:
            name = desc
            remark = " ".join(details).strip()
            
    # Caso o identificador venha vazio mas o nome pareça um CPF/CNPJ mascarado
    if not identifier and ('***.' in name or name.replace(' ', '').replace('.', '').replace('-', '').isdigit()):
        identifier = name
        name = ""
        
    return name, identifier, remark

def categorize_transaction(tx, name, identifier, remark):
    """
    Aplica as regras automáticas de categorização alinhadas com o usuário.
    """
    dc = tx['dc']
    desc = tx['description']
    val = tx['value']
    
    # Normalização para busca textual
    name_l = name.lower()
    remark_l = remark.lower()
    desc_l = desc.lower()

    if dc == 'C': # Recebimentos (Crédito)
        # 1. Rendimento de Capital
        if 'juros s/capital' in desc_l:
            return "Rendimento de Capital"
            
        # 2. Devolução / Estorno
        if 'estorno' in desc_l or 'devolução' in desc_l or 'devolucao' in desc_l:
            return "Devolução / Estorno"
            
        # 3. Inscrição Evento (XC AVLAC)
        if (re.search(r'xc\s*av[i]?lac', remark_l) or 
            re.search(r'inscri', remark_l) or 
            re.search(r'xc\s*av[i]?lac', name_l)):
            return "Inscrição Evento (XC AVLAC)"
            
        # 4. Anuidade
        if 'anuidade' in remark_l or 'mensalidade' in remark_l or 'anuidade' in desc_l:
            return "Anuidade"
            
        # Classificação por faixa de valor solicitada pelo usuário:
        # Faixa de R$ 30 a R$ 100 -> Inscrição Evento (XC AVLAC)
        if 30.0 <= val <= 100.0:
            return "Inscrição Evento (XC AVLAC)"

        # Acima de R$ 100 -> Anuidade
        if val > 100.0:
            return "Anuidade"

        # 5. Entrada sem classificação (empresas/CNPJs)
        is_cnpj = "0001" in identifier or "0001" in name or "ltda" in name_l or "s/a" in name_l or " Rest " in name or "restaurante" in name_l
        if is_cnpj:
            return "Entrada sem classificação"

        # 6. Outras Receitas (caso não bata em nada anterior, ex: valores abaixo de R$ 30)
        return "Outras Receitas"
        
    else: # Despesas (Débito)
        # 1. Reembolso despesas/Eventos (Frederico Randow - CPF ***.801.627-**)
        is_frederico = (identifier == '***.801.627-**' or 
                        'frederico' in name_l or 
                        'randow' in name_l or 
                        '***.801.627-**' in name)
        if is_frederico:
            return "Reembolso despesas/Eventos"
            
        # 2. Devolução Pix Enviada
        if 'devolução' in desc_l or 'devolucao' in desc_l:
            return "Devolução Pix Enviada"
            
        # 3. Tarifas Bancárias
        if 'pacote serviços' in desc_l or 'pacote servicos' in desc_l or 'título cobrança' in desc_l or 'titulo cobranca' in desc_l:
            return "Tarifas Bancárias"
            
        # 4. Internet Estação (Scherrernet)
        if 'scherrernet' in name_l:
            return "Internet Estação"
            
        # 5. Manutenção da Estação / Rampa
        is_station_maintenance = ('estacao metereologica' in remark_l or 
                                  'estação' in remark_l or 
                                  'mastro' in remark_l or 
                                  'sol sports' in name_l or 
                                  '85.255.743 0001-65' in identifier or 
                                  '85.255.743 0001-65' in name)
        if is_station_maintenance:
            return "Manutenção da Estação / Rampa"
            
        # 6. Despesa Evento (Confraternização / Troféus / Camisas)
        is_event_expense = ('festa' in remark_l or 
                            'churrasc' in remark_l or 
                            'churrasq' in remark_l or 
                            'tropeiro' in remark_l or 
                            'cerveja' in remark_l or 
                            'carvao' in remark_l or 
                            'carvão' in remark_l or 
                            'banda' in remark_l or 
                            'cache' in remark_l or 
                            'cachê' in remark_l or 
                            'musica' in remark_l or 
                            'som' in remark_l or 
                            'bruxo' in remark_l or
                            'casa do acrilico' in name_l or 
                            '40.612.231 0001-70' in identifier or 
                            'mar azul' in name_l or 
                            '48.024.083 0001-85' in identifier or 
                            'tom & cor' in name_l or 
                            'brandini' in name_l or 
                            '36.320.364 0001-04' in identifier)
        if is_event_expense:
            return "Despesa Evento (Confraternização / Troféus / Camisas)"
            
        # 7. Serviços Prestados / Limpeza (Lucinete Siqueira)
        if 'lucinete' in name_l:
            return "Serviços Prestados / Limpeza"
            
        # 8. Despesa a Categorizar / Outras
        return "Despesa a Categorizar / Outras"

def generate_markdown_report(processed_txs, report_path, statement_name, balances_data):
    """
    Gera um relatório financeiro Markdown completo agrupado por ano,
    incluindo saldos iniciais/finais e blocos <details> colapsáveis para as transações.
    """
    # Agrupar por ano
    txs_by_year = defaultdict(list)
    for tx in processed_txs:
        year = tx['Data'].split('/')[-1]
        txs_by_year[year].append(tx)
        
    years = sorted(list(txs_by_year.keys()))

    with open(report_path, 'w', encoding='utf-8') as rf:
        rf.write(f"# Relatório Financeiro AVLAC\n\n")
        rf.write(f"Gerado automaticamente a partir do extrato: `{statement_name}`\n\n")
        
        # Menu de links
        rf.write("### 📅 Navegação por Ano\n")
        rf.write(" | ".join([f"[{yr}](#-ano-{yr})" for yr in years]) + " | [Visão Consolidada (Todos os Anos)](#-visao-consolidada-todos-os-anos)\n\n")
        rf.write("---\n\n")

        # 1. Visão por ano
        for yr in years:
            rf.write(f"## 📅 Ano {yr}\n\n")
            yr_txs = txs_by_year[yr]
            yr_bal = balances_data[yr]
            
            rf.write(f"| Tipo | Métrica | Valor |\n")
            rf.write(f"| :--- | :--- | :--- |\n")
            rf.write(f"| 🏦 | **Saldo Anterior (Início do Ano)** | **R$ {format_float_br(yr_bal['inicial'])}** |\n")
            rf.write(f"| 🟢 | Receitas do Ano | R$ {format_float_br(yr_bal['receitas'])} |\n")
            rf.write(f"| 🔴 | Despesas do Ano | R$ {format_float_br(yr_bal['despesas'])} |\n")
            rf.write(f"| ⚖️ | Saldo Líquido do Ano | R$ {format_float_br(yr_bal['liquido'])} |\n")
            rf.write(f"| 🏁 | **Saldo Final (Fim do Ano)** | **R$ {format_float_br(yr_bal['final'])}** |\n\n")
            
            # Agrupar por categoria no ano
            cat_summary = defaultdict(float)
            cat_counts = defaultdict(int)
            cat_txs = defaultdict(list)
            for t in yr_txs:
                cat = t['Categoria']
                cat_summary[cat] += t['Valor (R$)']
                cat_counts[cat] += 1
                cat_txs[cat].append(t)
                
            rf.write(f"### 🟢 Recebimentos de {yr}\n\n")
            receitas_cats = ["Anuidade", "Inscrição Evento (XC AVLAC)", "Rendimento de Capital", "Devolução / Estorno", "Entrada sem classificação", "Outras Receitas"]
            for cat in receitas_cats:
                if cat_counts[cat] > 0:
                    rf.write(f"<details>\n<summary><b>{cat}</b> ({cat_counts[cat]} txs): R$ {format_float_br(cat_summary[cat])} <i>(Clique para expandir)</i></summary>\n\n")
                    rf.write(f"| Data | Favorecido/Pagador | CPF/CNPJ | Valor | Comentário |\n")
                    rf.write(f"| :---: | :--- | :---: | :---: | :--- |\n")
                    for t in sorted(cat_txs[cat], key=lambda x: x['Data']):
                        rf.write(f"| {t['Data']} | {t['Payer_Favorecido']} | {t['CPF_CNPJ']} | R$ {format_float_br(t['Valor (R$)'])} | {t['Comentário Pix']} |\n")
                    rf.write(f"\n</details>\n\n")

            rf.write(f"### 🔴 Saídas (Despesas) de {yr}\n\n")
            despesas_cats = ["Tarifas Bancárias", "Reembolso despesas/Eventos", "Internet Estação", "Manutenção da Estação / Rampa", "Despesa Evento (Confraternização / Troféus / Camisas)", "Serviços Prestados / Limpeza", "Devolução Pix Enviada", "Despesa a Categorizar / Outras"]
            for cat in despesas_cats:
                if cat_counts[cat] > 0:
                    rf.write(f"<details>\n<summary><b>{cat}</b> ({cat_counts[cat]} txs): R$ {format_float_br(cat_summary[cat])} <i>(Clique para expandir)</i></summary>\n\n")
                    rf.write(f"| Data | Favorecido/Pagador | CPF/CNPJ | Valor | Comentário |\n")
                    rf.write(f"| :---: | :--- | :---: | :---: | :--- |\n")
                    for t in sorted(cat_txs[cat], key=lambda x: x['Data']):
                        rf.write(f"| {t['Data']} | {t['Payer_Favorecido']} | {t['CPF_CNPJ']} | R$ {format_float_br(t['Valor (R$)'])} | {t['Comentário Pix']} |\n")
                    rf.write(f"\n</details>\n\n")
            
            rf.write("---\n\n")

        # 2. Visão Consolidada de todos os anos
        rf.write(f"## 📊 Visão Consolidada (Todos os Anos)\n\n")
        total_bal = balances_data['Todos']
        
        rf.write(f"| Tipo | Métrica | Valor |\n")
        rf.write(f"| :--- | :--- | :--- |\n")
        rf.write(f"| 🏦 | **Saldo Inicial do Extrato** | **R$ {format_float_br(total_bal['inicial'])}** |\n")
        rf.write(f"| 🟢 | Total de Receitas (Créditos) | R$ {format_float_br(total_bal['receitas'])} |\n")
        rf.write(f"| 🔴 | Total de Despesas (Débitos) | R$ {format_float_br(total_bal['despesas'])} |\n")
        rf.write(f"| ⚖️ | Saldo Líquido Consolidado | R$ {format_float_br(total_bal['liquido'])} |\n")
        rf.write(f"| 🏁 | **Saldo Final do Extrato** | **R$ {format_float_br(total_bal['final'])}** |\n\n")
        
        # Agrupamento global de categorias
        g_summary = defaultdict(float)
        g_counts = defaultdict(int)
        for t in processed_txs:
            g_summary[t['Categoria']] += t['Valor (R$)']
            g_counts[t['Categoria']] += 1
            
        rf.write(f"### Receitas Totais por Categoria\n\n")
        for cat in receitas_cats:
            if g_counts[cat] > 0:
                rf.write(f" - **{cat}** ({g_counts[cat]} txs): R$ {format_float_br(g_summary[cat])}\n")
                
        rf.write(f"\n### Despesas Totais por Categoria\n\n")
        for cat in despesas_cats:
            if g_counts[cat] > 0:
                rf.write(f" - **{cat}** ({g_counts[cat]} txs): R$ {format_float_br(g_summary[cat])}\n")

def generate_html_dashboard(processed_txs, html_path, statement_name, balances_data):
    """
    Gera um dashboard HTML/JS dinâmico e premium (com Tailwind CSS, gráficos circulares
    de progresso e pesquisa/filtro interativo) contendo todas as transações da AVLAC,
    exibindo detalhadamente os Saldos Anterior, Líquido e Final.
    """
    # Enriquecer transações com ano para facilidade no JS
    enriched_txs = []
    for tx in processed_txs:
        t = tx.copy()
        t['year'] = tx['Data'].split('/')[-1]
        enriched_txs.append(t)
        
    transactions_json = json.dumps(enriched_txs, ensure_ascii=False)
    balances_json = json.dumps(balances_data, ensure_ascii=False)

    html_content = f"""<!DOCTYPE html>
<html lang="pt-BR" class="h-full bg-slate-950 text-slate-100">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Painel Financeiro - AVLAC</title>
    <!-- Tailwind CSS CDN -->
    <script src="https://cdn.tailwindcss.com"></script>
    <!-- FontAwesome for icons -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <!-- Google Fonts Outfit & Inter -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
    <script>
        tailwind.config = {{
            theme: {{
                extend: {{
                    fontFamily: {{
                        sans: ['Inter', 'sans-serif'],
                        title: ['Outfit', 'sans-serif'],
                    }}
                }}
            }}
        }}
    </script>
    <style>
        .glass {{
            background: rgba(15, 23, 42, 0.65);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.05);
        }}
        .card-glow {{
            transition: all 0.3s ease;
        }}
        .card-glow:hover {{
            box-shadow: 0 0 20px 0 rgba(14, 165, 233, 0.15);
            transform: translateY(-2px);
        }}
        /* Personalização do scrollbar */
        ::-webkit-scrollbar {{
            width: 8px;
            height: 8px;
        }}
        ::-webkit-scrollbar-track {{
            background: #020617;
        }}
        ::-webkit-scrollbar-thumb {{
            background: #1e293b;
            border-radius: 4px;
        }}
        ::-webkit-scrollbar-thumb:hover {{
            background: #334155;
        }}
    </style>
</head>
<body class="font-sans min-h-screen flex flex-col bg-[radial-gradient(ellipse_80%_80%_at_50%_-20%,rgba(14,165,233,0.12),rgba(255,255,255,0))]">
    
    <!-- Header -->
    <header class="border-b border-slate-900 bg-slate-950/80 sticky top-0 z-50 backdrop-blur-md">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div class="flex items-center gap-3">
                <div class="w-12 h-12 rounded-xl bg-gradient-to-tr from-sky-500 to-indigo-600 flex items-center justify-center text-white text-2xl shadow-lg shadow-sky-500/20">
                    <i class="fa-solid fa-wind"></i>
                </div>
                <div>
                    <h1 class="font-title font-bold text-2xl tracking-tight text-white">AVLAC</h1>
                    <p class="text-xs text-slate-400">Associação de Voo Livre de Alfredo Chaves</p>
                </div>
            </div>
            
            <!-- Ações integradas no cabeçalho -->
            <div class="flex flex-wrap items-center gap-2">
                <a href="./relatorio.md" class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-800/80 transition-colors">
                    <i class="fa-solid fa-file-invoice text-indigo-400"></i> Relatório MD
                </a>
                <a href="./extrato_processado.csv" download class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-800/80 transition-colors">
                    <i class="fa-solid fa-file-csv text-emerald-400"></i> Baixar CSV
                </a>
                <span class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium bg-slate-900 text-slate-400 border border-slate-800/80">
                    <i class="fa-solid fa-file-invoice"></i> Extrato: {statement_name}
                </span>
            </div>
        </div>
    </header>

    <!-- Main Content -->
    <main class="flex-grow max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 w-full">
        
        <!-- Tabs de Ano -->
        <div class="flex items-center gap-2 mb-8 bg-slate-900/60 p-1.5 rounded-xl w-fit border border-slate-800/80">
            <button onclick="changeYear('Todos')" id="tab-Todos" class="px-4 py-2 text-sm font-medium rounded-lg transition-all duration-200 text-sky-400 bg-slate-950/80 border border-slate-800">
                Todos os Anos
            </button>
            <button onclick="changeYear('2025')" id="tab-2025" class="px-4 py-2 text-sm font-medium rounded-lg transition-all duration-200 text-slate-400 hover:text-slate-200">
                2025
            </button>
            <button onclick="changeYear('2026')" id="tab-2026" class="px-4 py-2 text-sm font-medium rounded-lg transition-all duration-200 text-slate-400 hover:text-slate-200">
                2026
            </button>
        </div>

        <!-- Metric Cards -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            <!-- Receitas -->
            <div class="glass card-glow rounded-2xl p-6 relative overflow-hidden">
                <div class="absolute top-0 right-0 w-24 h-24 bg-emerald-500/5 rounded-bl-full pointer-events-none"></div>
                <div class="flex items-center justify-between mb-4">
                    <span class="text-sm font-medium text-slate-400">Total Receitas</span>
                    <div class="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center text-emerald-400">
                        <i class="fa-solid fa-arrow-trend-up"></i>
                    </div>
                </div>
                <div class="text-3xl font-title font-bold text-emerald-400" id="total-receitas">R$ 0,00</div>
                <div class="text-xs text-slate-500 mt-2" id="receitas-count">0 transações</div>
            </div>

            <!-- Despesas -->
            <div class="glass card-glow rounded-2xl p-6 relative overflow-hidden">
                <div class="absolute top-0 right-0 w-24 h-24 bg-rose-500/5 rounded-bl-full pointer-events-none"></div>
                <div class="flex items-center justify-between mb-4">
                    <span class="text-sm font-medium text-slate-400">Total Despesas</span>
                    <div class="w-8 h-8 rounded-lg bg-rose-500/10 flex items-center justify-center text-rose-400">
                        <i class="fa-solid fa-arrow-trend-down"></i>
                    </div>
                </div>
                <div class="text-3xl font-title font-bold text-rose-400" id="total-despesas">R$ 0,00</div>
                <div class="text-xs text-slate-500 mt-2" id="despesas-count">0 transações</div>
            </div>

            <!-- Saldo Líquido -->
            <div class="glass card-glow rounded-2xl p-6 relative overflow-hidden">
                <div class="absolute top-0 right-0 w-24 h-24 bg-sky-500/5 rounded-bl-full pointer-events-none"></div>
                <div class="flex items-center justify-between mb-2">
                    <span class="text-sm font-medium text-slate-400 font-semibold">Fluxo de Caixa</span>
                    <div class="w-8 h-8 rounded-lg bg-sky-500/10 flex items-center justify-center text-sky-400" id="saldo-icon">
                        <i class="fa-solid fa-scale-balanced"></i>
                    </div>
                </div>
                <div class="text-3xl font-title font-bold text-white mb-2" id="total-saldo">R$ 0,00</div>
                
                <div class="text-[11px] text-slate-400 flex flex-col gap-1 border-t border-slate-900 pt-2" id="saldo-details">
                    <div class="flex justify-between">
                        <span class="text-slate-500">Saldo Inicial:</span> 
                        <span id="saldo-inicial" class="font-mono text-slate-300 font-medium">R$ 0,00</span>
                    </div>
                    <div class="flex justify-between">
                        <span class="text-slate-500">Saldo Final:</span> 
                        <span id="saldo-final" class="font-mono text-slate-300 font-medium">R$ 0,00</span>
                    </div>
                </div>
            </div>
        </div>

        <!-- Two Columns Layout -->
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
            
            <!-- Column 1: Categoria Breakdown -->
            <div class="lg:col-span-1 flex flex-col gap-6">
                <div class="glass rounded-2xl p-6">
                    <h3 class="font-title font-semibold text-lg text-white mb-6 flex items-center gap-2">
                        <i class="fa-solid fa-chart-pie text-sky-500"></i> Receitas por Categoria
                    </h3>
                    <div class="flex flex-col gap-4" id="receitas-breakdown">
                        <!-- Progress bars -->
                    </div>
                </div>

                <div class="glass rounded-2xl p-6">
                    <h3 class="font-title font-semibold text-lg text-white mb-6 flex items-center gap-2">
                        <i class="fa-solid fa-chart-bar text-rose-500"></i> Despesas por Categoria
                    </h3>
                    <div class="flex flex-col gap-4" id="despesas-breakdown">
                        <!-- Progress bars -->
                    </div>
                </div>
            </div>

            <!-- Column 2 & 3: Interactive Table -->
            <div class="lg:col-span-2 flex flex-col gap-6">
                <div class="glass rounded-2xl p-6">
                    
                    <!-- Filtros e Pesquisa -->
                    <div class="flex flex-col sm:flex-row gap-4 mb-6">
                        <div class="flex-grow relative">
                            <i class="fa-solid fa-magnifying-glass absolute left-3 top-3.5 text-slate-500"></i>
                            <input type="text" id="search-input" placeholder="Pesquisar por pagador, comentário ou documento..." 
                                   class="w-full pl-10 pr-4 py-2.5 rounded-xl bg-slate-900/60 border border-slate-800 focus:outline-none focus:border-sky-500 text-sm text-slate-200 placeholder-slate-500">
                        </div>
                        <div class="flex gap-4">
                            <select id="type-filter" class="px-4 py-2.5 rounded-xl bg-slate-900/60 border border-slate-800 text-sm text-slate-300 focus:outline-none focus:border-sky-500">
                                <option value="Todos">Todos Fluxos</option>
                                <option value="Crédito">Entradas (Créditos)</option>
                                <option value="Débito">Saídas (Débitos)</option>
                            </select>
                            <select id="category-filter" class="px-4 py-2.5 rounded-xl bg-slate-900/60 border border-slate-800 text-sm text-slate-300 focus:outline-none focus:border-sky-500 max-w-[150px] sm:max-w-xs">
                                <option value="Todos">Todas Categorias</option>
                                <!-- Categories populated by JS -->
                            </select>
                        </div>
                    </div>

                    <!-- Tabela de Transações -->
                    <div class="overflow-x-auto rounded-xl border border-slate-900">
                        <table class="min-w-full divide-y divide-slate-900 text-sm text-left">
                            <thead class="bg-slate-900/40 text-slate-400 font-medium text-xs uppercase tracking-wider">
                                <tr>
                                    <th class="px-4 py-3.5">Data</th>
                                    <th class="px-4 py-3.5">Beneficiário/Origem</th>
                                    <th class="px-4 py-3.5">Categoria</th>
                                    <th class="px-4 py-3.5 text-right">Valor</th>
                                    <th class="px-2 py-3.5 text-center">Ações</th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-slate-900 bg-slate-950/20" id="transactions-body">
                                <!-- Populated dynamically -->
                            </tbody>
                        </table>
                    </div>
                    
                    <div class="flex justify-between items-center text-xs text-slate-500 mt-4">
                        <span id="showing-count">Mostrando 0 de 0 transações</span>
                    </div>

                </div>
            </div>

        </div>

    </main>

    <!-- Footer -->
    <footer class="border-t border-slate-900 py-6 mt-16 bg-slate-950">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center text-xs text-slate-500 flex flex-col sm:flex-row sm:justify-between items-center gap-4">
            <div>
                © 2026 AVLAC - Associação de Voo Livre de Alfredo Chaves. Todos os direitos reservados.
            </div>
            <div class="flex items-center gap-4">
                Desenvolvido para Prestação de Contas
            </div>
        </div>
    </footer>

    <!-- JS Logic -->
    <script>
        const transactions = {transactions_json};
        const balances = {balances_json};
        
        let currentYear = 'Todos';
        
        // Formata Moeda
        function formatMoney(value) {{
            return new Intl.NumberFormat('pt-BR', {{ style: 'currency', currency: 'BRL' }}).format(value);
        }}

        // Inicializador
        document.addEventListener('DOMContentLoaded', () => {{
            populateCategoryFilter();
            renderDashboard();
            
            document.getElementById('search-input').addEventListener('input', renderDashboard);
            document.getElementById('type-filter').addEventListener('change', renderDashboard);
            document.getElementById('category-filter').addEventListener('change', renderDashboard);
        }});

        function populateCategoryFilter() {{
            const categories = [...new Set(transactions.map(t => t.Categoria))].sort();
            const filter = document.getElementById('category-filter');
            categories.forEach(cat => {{
                const opt = document.createElement('option');
                opt.value = cat;
                opt.textContent = cat;
                filter.appendChild(opt);
            }});
        }}

        function changeYear(year) {{
            document.getElementById(`tab-${{currentYear}}`).className = "px-4 py-2 text-sm font-medium rounded-lg transition-all duration-200 text-slate-400 hover:text-slate-200";
            currentYear = year;
            document.getElementById(`tab-${{year}}`).className = "px-4 py-2 text-sm font-medium rounded-lg transition-all duration-200 text-sky-400 bg-slate-950/80 border border-slate-800";
            renderDashboard();
        }}

        function toggleDetails(index) {{
            const el = document.getElementById(`details-${{index}}`);
            const icon = document.getElementById(`icon-${{index}}`);
            if (el.classList.contains('hidden')) {{
                el.classList.remove('hidden');
                icon.className = "fa-solid fa-chevron-up transition-transform";
            }} else {{
                el.classList.add('hidden');
                icon.className = "fa-solid fa-chevron-down transition-transform";
            }}
        }}

        function renderDashboard() {{
            const search = document.getElementById('search-input').value.toLowerCase();
            const type = document.getElementById('type-filter').value;
            const category = document.getElementById('category-filter').value;

            // Filtrar
            const filtered = transactions.filter(t => {{
                const matchesYear = currentYear === 'Todos' || t.year === currentYear;
                
                const matchesSearch = t.Payer_Favorecido.toLowerCase().includes(search) || 
                                      t['Descrição Sicoob'].toLowerCase().includes(search) ||
                                      t['Comentário Pix'].toLowerCase().includes(search) ||
                                      t.Documento.toLowerCase().includes(search);
                                      
                const matchesType = type === 'Todos' || t.Tipo === type;
                const matchesCategory = category === 'Todos' || t.Categoria === category;
                
                return matchesYear && matchesSearch && matchesType && matchesCategory;
            }});

            // Calcular Métricas Filtradas
            let yrInflows = 0;
            let yrInflowsCount = 0;
            let yrOutflows = 0;
            let yrOutflowsCount = 0;

            const categoryTotals = {{}};
            const categoryTypes = {{}};

            filtered.forEach(t => {{
                const val = t['Valor (R$)'];
                if (t.Tipo === 'Crédito') {{
                    yrInflows += val;
                    yrInflowsCount++;
                }} else {{
                    yrOutflows += val;
                    yrOutflowsCount++;
                }}

                categoryTotals[t.Categoria] = (categoryTotals[t.Categoria] || 0) + val;
                categoryTypes[t.Categoria] = t.Tipo;
            }});

            // Obter dados oficiais de saldo para o ano corrente (de acordo com o livro-caixa completo)
            const balInfo = balances[currentYear];

            // Renderizar Números baseados nos filtros ativos
            const hasActiveSearchFilter = search !== '' || type !== 'Todos' || category !== 'Todos';
            const displayInflows = hasActiveSearchFilter ? yrInflows : balInfo.receitas;
            const displayOutflows = hasActiveSearchFilter ? yrOutflows : balInfo.despesas;
            const displayBalance = hasActiveSearchFilter ? (yrInflows - yrOutflows) : balInfo.liquido;

            document.getElementById('total-receitas').textContent = formatMoney(displayInflows);
            document.getElementById('receitas-count').textContent = hasActiveSearchFilter ? `${{yrInflowsCount}} filtradas` : `${{yrInflowsCount}} transações`;
            
            document.getElementById('total-despesas').textContent = formatMoney(displayOutflows);
            document.getElementById('despesas-count').textContent = hasActiveSearchFilter ? `${{yrOutflowsCount}} filtradas` : `${{yrOutflowsCount}} transações`;
            
            const saldoEl = document.getElementById('total-saldo');
            const saldoIcon = document.getElementById('saldo-icon');
            saldoEl.textContent = (displayBalance >= 0 ? '+' : '') + formatMoney(displayBalance);
            
            if (displayBalance >= 0) {{
                saldoEl.className = "text-3xl font-title font-bold text-emerald-400 mb-2";
                saldoIcon.className = "w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center text-emerald-400";
            }} else {{
                saldoEl.className = "text-3xl font-title font-bold text-rose-400 mb-2";
                saldoIcon.className = "w-8 h-8 rounded-lg bg-rose-500/10 flex items-center justify-center text-rose-400";
            }}

            // Atualizar Saldo Inicial e Final
            document.getElementById('saldo-inicial').textContent = formatMoney(balInfo.inicial);
            document.getElementById('saldo-final').textContent = formatMoney(balInfo.final);

            // Renderizar Progress Bars de Categorias
            const recBreakdown = document.getElementById('receitas-breakdown');
            const despBreakdown = document.getElementById('despesas-breakdown');
            
            recBreakdown.innerHTML = '';
            despBreakdown.innerHTML = '';

            // Ordenar categorias por valor decrescente
            const sortedCats = Object.keys(categoryTotals).sort((a,b) => categoryTotals[b] - categoryTotals[a]);
            
            let maxRec = 0;
            let maxDesp = 0;
            sortedCats.forEach(cat => {{
                if (categoryTypes[cat] === 'Crédito' && categoryTotals[cat] > maxRec) maxRec = categoryTotals[cat];
                if (categoryTypes[cat] === 'Débito' && categoryTotals[cat] > maxDesp) maxDesp = categoryTotals[cat];
            }});

            sortedCats.forEach(cat => {{
                const val = categoryTotals[cat];
                const type = categoryTypes[cat];
                
                const barHtml = `
                    <div>
                        <div class="flex justify-between text-xs font-medium mb-1">
                            <span class="text-slate-300 hover:text-white transition-colors cursor-pointer" onclick="document.getElementById('category-filter').value='${{cat}}'; renderDashboard();">${{cat}}</span>
                            <span class="${{type === 'Crédito' ? 'text-emerald-400' : 'text-rose-400'}}">${{formatMoney(val)}}</span>
                        </div>
                        <div class="w-full bg-slate-950 rounded-full h-2 border border-slate-900">
                            <div class="h-full rounded-full ${{type === 'Crédito' ? 'bg-emerald-500' : 'bg-rose-500'}}" style="width: ${{((val / (type === 'Crédito' ? maxRec : maxDesp)) * 100) || 0}}%"></div>
                        </div>
                    </div>
                `;
                
                if (type === 'Crédito') {{
                    recBreakdown.insertAdjacentHTML('beforeend', barHtml);
                }} else {{
                    despBreakdown.insertAdjacentHTML('beforeend', barHtml);
                }}
            }});

            if (recBreakdown.innerHTML === '') {{
                recBreakdown.innerHTML = '<div class="text-xs text-slate-500 italic text-center py-4">Sem entradas para este filtro</div>';
            }}
            if (despBreakdown.innerHTML === '') {{
                despBreakdown.innerHTML = '<div class="text-xs text-slate-500 italic text-center py-4">Sem saídas para este filtro</div>';
            }}

            // Renderizar Tabela
            const tbody = document.getElementById('transactions-body');
            tbody.innerHTML = '';

            filtered.forEach((t, idx) => {{
                const rowId = `row-${{idx}}`;
                const detailsId = `details-${{idx}}`;
                const isCredit = t.Tipo === 'Crédito';
                
                const trHtml = `
                    <tr class="hover:bg-slate-900/20 transition-colors cursor-pointer" onclick="toggleDetails(${{idx}})">
                        <td class="px-4 py-3.5 text-slate-300 font-mono text-xs whitespace-nowrap">${{t.Data}}</td>
                        <td class="px-4 py-3.5">
                            <div class="font-medium text-slate-200">${{t.Payer_Favorecido}}</div>
                            <div class="text-[10px] text-slate-500 font-mono">${{t.CPF_CNPJ || t['Descrição Sicoob']}}</div>
                        </td>
                        <td class="px-4 py-3.5 whitespace-nowrap">
                            <span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border border-slate-800 ${{isCredit ? 'bg-emerald-950/20 text-emerald-400 border-emerald-500/20' : 'bg-rose-950/20 text-rose-400 border-rose-500/20'}}">
                                ${{t.Categoria}}
                            </span>
                        </td>
                        <td class="px-4 py-3.5 text-right font-semibold whitespace-nowrap ${{isCredit ? 'text-emerald-400' : 'text-slate-300'}}">
                            ${{isCredit ? '+' : '-'}} ${{formatMoney(t['Valor (R$)'])}}
                        </td>
                        <td class="px-2 py-3.5 text-center">
                            <button class="w-7 h-7 rounded-lg bg-slate-900 hover:bg-slate-800 flex items-center justify-center text-slate-400 hover:text-slate-200 transition-colors">
                                <i id="icon-${{idx}}" class="fa-solid fa-chevron-down text-xs transition-transform"></i>
                            </button>
                        </td>
                    </tr>
                    <tr id="${{detailsId}}" class="hidden bg-slate-900/10">
                        <td colspan="5" class="px-6 py-4 border-t border-slate-900/60">
                            <div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                                <div>
                                    <div class="text-slate-500 font-medium uppercase tracking-wider text-[10px] mb-1">Informações do Extrato</div>
                                    <div class="flex flex-col gap-1 text-slate-300">
                                        <div><span class="text-slate-500">Documento Sicoob:</span> ${{t.Documento}}</div>
                                        <div><span class="text-slate-500">Descrição Original:</span> ${{t['Descrição Sicoob']}}</div>
                                        <div><span class="text-slate-500">Valor Lançado:</span> R$ ${{t['Valor (R$)']}} (${{t.Tipo === 'Crédito' ? 'Crédito/C' : 'Débito/D'}})</div>
                                    </div>
                                </div>
                                <div>
                                    <div class="text-slate-500 font-medium uppercase tracking-wider text-[10px] mb-1">Detalhes Adicionais (Favorecido / Mensagem)</div>
                                    <div class="flex flex-col gap-1 text-slate-300">
                                        <div><span class="text-slate-500">Favorecido:</span> ${{t.Payer_Favorecido}}</div>
                                        <div><span class="text-slate-500">CPF/CNPJ:</span> ${{t.CPF_CNPJ || 'Não informado'}}</div>
                                        <div class="mt-2 p-2 rounded bg-slate-950/60 border border-slate-900 text-sky-400">
                                            <span class="text-slate-500 block text-[10px] uppercase font-semibold mb-0.5">Comentário Pix:</span>
                                            ${{t['Comentário Pix'] || '<span class="italic text-slate-600">Sem comentário enviado</span>'}}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </td>
                    </tr>
                `;
                tbody.insertAdjacentHTML('beforeend', trHtml);
            }});

            if (filtered.length === 0) {{
                tbody.innerHTML = `
                    <tr>
                        <td colspan="5" class="px-4 py-8 text-center text-slate-500 italic">
                            Nenhuma transação encontrada com os filtros atuais.
                        </td>
                    </tr>
                `;
            }}

            document.getElementById('showing-count').textContent = `Mostrando ${{filtered.length}} de ${{transactions.length}} transações`;
        }}

    </script>
</body>
</html>
"""
    with open(html_path, 'w', encoding='utf-8') as hf:
        hf.write(html_content)


def main():
    # Caminho do extrato pode ser passado por argumento ou assume o padrão da pasta
    script_dir = os.path.dirname(os.path.abspath(__file__))
    txt_dir = os.path.join(script_dir, "txt")
    
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        # Tenta achar o arquivo merged padrão na pasta txt/
        if os.path.exists(txt_dir):
            files = [os.path.join(txt_dir, f) for f in os.listdir(txt_dir) if f.endswith('.txt')]
            if files:
                file_path = files[0]
            else:
                print("Nenhum arquivo .txt encontrado na pasta 'txt/'. Por favor passe o caminho do arquivo por parâmetro.")
                sys.exit(1)
        else:
            print(f"Pasta 'txt/' não encontrada em {txt_dir}. Por favor passe o caminho do arquivo por parâmetro.")
            sys.exit(1)

    print(f"Processando extrato bancário de: {file_path}")
    raw_txs = parse_sicoob_statement(file_path)
    print(f"Lidas {len(raw_txs)} movimentações.")

    # Descobrir o Saldo Inicial do período
    initial_balance = find_initial_balance(file_path)

    processed_txs = []
    category_summary = defaultdict(float)
    category_counts = defaultdict(int)
    
    total_inflows = 0.0
    total_outflows = 0.0

    for tx in raw_txs:
        # Extrair campos semânticos dos detalhes
        name, identifier, remark = extract_fields(tx)
        
        # Categorizar
        category = categorize_transaction(tx, name, identifier, remark)
        
        # Adicionar à lista
        tx_processed = {
            'Data': tx['date'],
            'Documento': tx['doc'],
            'Descrição Sicoob': tx['description'],
            'Payer_Favorecido': name or identifier or "N/D",
            'CPF_CNPJ': identifier if name else "",
            'Comentário Pix': remark,
            'Tipo': "Crédito" if tx['dc'] == 'C' else "Débito",
            'Valor (R$)': tx['value'],
            'Categoria': category
        }
        processed_txs.append(tx_processed)
        
        # Consolidação financeira
        val = tx['value']
        if tx['dc'] == 'C':
            total_inflows += val
            category_summary[category] += val
        else:
            total_outflows += val
            category_summary[category] += val  # Mantém positivo no consolidado por categoria
            
        category_counts[category] += 1

    # Corrigindo contagem por categoria de forma simplificada
    category_counts.clear()
    for tx in processed_txs:
        category_counts[tx['Categoria']] += 1

    # Agrupar transações por ano e calcular balanços anuais detalhados
    txs_by_year = defaultdict(list)
    for tx in processed_txs:
        year = tx['Data'].split('/')[-1]
        txs_by_year[year].append(tx)
        
    years = sorted(list(txs_by_year.keys()))
    
    balances_data = {}
    current_init = initial_balance
    
    for yr in years:
        yr_txs = txs_by_year[yr]
        inflows = sum(t['Valor (R$)'] for t in yr_txs if t['Tipo'] == 'Crédito')
        outflows = sum(t['Valor (R$)'] for t in yr_txs if t['Tipo'] == 'Débito')
        liq = inflows - outflows
        fin = current_init + liq
        
        balances_data[yr] = {
            'inicial': current_init,
            'receitas': inflows,
            'despesas': outflows,
            'liquido': liq,
            'final': fin
        }
        current_init = fin
        
    # Consolidado geral "Todos"
    total_inflows = sum(t['Valor (R$)'] for t in processed_txs if t['Tipo'] == 'Crédito')
    total_outflows = sum(t['Valor (R$)'] for t in processed_txs if t['Tipo'] == 'Débito')
    total_liq = total_inflows - total_outflows
    total_fin = initial_balance + total_liq
    
    balances_data['Todos'] = {
        'inicial': initial_balance,
        'receitas': total_inflows,
        'despesas': total_outflows,
        'liquido': total_liq,
        'final': total_fin
    }

    # 1. Exportar para CSV formatado para Excel
    output_csv_path = os.path.join(script_dir, "extrato_processado.csv")
    with open(output_csv_path, 'w', encoding='utf-8-sig', newline='') as csvfile:
        fieldnames = ['Data', 'Documento', 'Descrição Sicoob', 'Payer_Favorecido', 'CPF_CNPJ', 'Comentário Pix', 'Tipo', 'Valor (R$)', 'Categoria']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=';')
        writer.writeheader()
        
        for tx in processed_txs:
            tx_csv = tx.copy()
            tx_csv['Valor (R$)'] = format_float_br(tx['Valor (R$)'])
            writer.writerow(tx_csv)

    print(f"Exportado com sucesso para: {output_csv_path}")

    # 2. Gerar relatório detalhado em Markdown agrupado por ano e expandível
    report_path = os.path.join(script_dir, "relatorio.md")
    generate_markdown_report(processed_txs, report_path, os.path.basename(file_path), balances_data)
    print(f"Relatório detalhado colapsável salvo em: {report_path}")

    # 3. Gerar Dashboard HTML interativo
    dashboard_path = os.path.join(script_dir, "index.html")
    generate_html_dashboard(processed_txs, dashboard_path, os.path.basename(file_path), balances_data)
    print(f"Dashboard HTML interativo gerado em: {dashboard_path}")

    # Exibição do resumo consolidado geral no terminal
    print("\n" + "="*50)
    print("                RESUMO FINANCEIRO AVLAC")
    print("="*50)
    print(f"Total de Transações: {len(processed_txs)}")
    print(f"Saldo Inicial:               R$ {format_float_br(initial_balance)}")
    print(f"Total de Receitas (Créditos): R$ {format_float_br(total_inflows)}")
    print(f"Total de Despesas (Débitos): R$ {format_float_br(total_outflows)}")
    print(f"Saldo Líquido no Período:    R$ {format_float_br(total_liq)}")
    print(f"Saldo Final:                 R$ {format_float_br(total_fin)}")
    print("-"*50)
    print("RESUMO CONSOLIDADO POR CATEGORIA:")
    
    print("\n--- RECEBIMENTOS (RECEITAS) ---")
    receitas_cats = ["Anuidade", "Inscrição Evento (XC AVLAC)", "Rendimento de Capital", "Devolução / Estorno", "Entrada sem classificação", "Outras Receitas"]
    for cat in receitas_cats:
        if category_counts[cat] > 0:
            print(f" - {cat:<32} ({category_counts[cat]:>3} txs): R$ {format_float_br(category_summary[cat]):>10}")

    print("\n--- SAÍDAS (DESPESAS) ---")
    despesas_cats = ["Tarifas Bancárias", "Reembolso despesas/Eventos", "Internet Estação", "Manutenção da Estação / Rampa", "Despesa Evento (Confraternização / Troféus / Camisas)", "Serviços Prestados / Limpeza", "Devolução Pix Enviada", "Despesa a Categorizar / Outras"]
    for cat in despesas_cats:
        if category_counts[cat] > 0:
            print(f" - {cat:<32} ({category_counts[cat]:>3} txs): R$ {format_float_br(category_summary[cat]):>10}")
            
    print("="*50)

if __name__ == "__main__":
    main()
