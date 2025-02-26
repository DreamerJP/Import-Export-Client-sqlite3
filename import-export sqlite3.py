import sqlite3
import os
import xml.etree.ElementTree as ET
import argparse
import sys
import time
import traceback
# Modifique a linha de importação do datetime para:
from datetime import datetime

# Para detecção de teclas em diferentes plataformas
try:
    # Windows
    import msvcrt
    def getch():
        return msvcrt.getch().decode('utf-8', errors='ignore')
except ImportError:
    try:
        # Unix/Linux/MacOS
        import termios
        import tty
        def getch():
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                ch = sys.stdin.read(1)
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            return ch
    except ImportError:
        # Fallback
        def getch():
            return input("Pressione Enter para continuar...")

# Caminho para o database (ajuste conforme necessário)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.path.join(BASE_DIR, '..', 'Programa de Chamados', 'backend', 'database.db')

def get_db_connection():
    """Estabelece conexão com o banco de dados SQLite."""
    conn = sqlite3.connect(DATABASE)
    conn.execute('PRAGMA foreign_keys = ON')
    return conn

def show_error_report(operation, errors, details=None):
    """
    Exibe um relatório detalhado de erros.
    
    Args:
        operation (str): Tipo de operação (importação/exportação)
        errors (list): Lista de erros encontrados
        details (dict, optional): Detalhes adicionais da operação
    """
    os.system('cls' if os.name == 'nt' else 'clear')
    print("\n┌─────────────────────────────────────────────────────────────┐")
    print("│                    RELATÓRIO DE ERROS                       │")
    print("└─────────────────────────────────────────────────────────────┘")
    print(f"\nOperação: {operation}")
    print(f"Data/Hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    
    if details:
        print("\nDetalhes da Operação:")
        for key, value in details.items():
            print(f"  {key}: {value}")
    
    print("\nErros Encontrados:")
    for i, error in enumerate(errors, 1):
        print(f"\n{i}. Tipo de Erro: {error.get('type', 'Desconhecido')}")
        print(f"   Descrição: {error.get('message', 'Sem descrição')}")
        if error.get('data'):
            print(f"   Dados Afetados: {error['data']}")
        if error.get('suggestion'):
            print(f"   Sugestão: {error['suggestion']}")
    
    print("\nPressione qualquer tecla para continuar...")
    getch()

def check_directory_permissions(directory):
    """
    Verifica permissões do diretório.
    Retorna (bool, str) - (sucesso, mensagem de erro)
    """
    try:
        # Cria o diretório se não existir
        if not os.path.exists(directory):
            os.makedirs(directory)
            
        # Testa permissão de escrita
        test_file = os.path.join(directory, '__test_write__.tmp')
        try:
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            return True, None
        except (IOError, OSError) as e:
            return False, f"Sem permissão de escrita: {str(e)}"
            
    except Exception as e:
        return False, f"Erro ao verificar diretório: {str(e)}"

def verify_xml_path(file_path, mode='w'):
    """
    Verifica se o caminho para o arquivo XML é válido e tem permissões corretas.
    mode: 'w' para escrita, 'r' para leitura
    Retorna (bool, str) - (sucesso, mensagem de erro)
    """
    try:
        # Validações básicas
        if not file_path:
            return False, "Caminho não especificado"
            
        if file_path.strip() in ['c:/', 'c:', '/', '\\']:
            return False, "Caminho inválido (raiz do sistema)"
            
        # Garante extensão .xml
        if not file_path.lower().endswith('.xml'):
            file_path += '.xml'
            
        directory = os.path.dirname(file_path)
        
        # Para leitura, verifica se o arquivo existe
        if mode == 'r':
            if not os.path.exists(file_path):
                return False, f"Arquivo não encontrado: {file_path}"
            if not os.access(file_path, os.R_OK):
                return False, f"Sem permissão de leitura: {file_path}"
            return True, None
            
        # Para escrita, verifica o diretório
        success, error = check_directory_permissions(directory)
        if not success:
            return False, error
            
        # Testa se pode escrever o arquivo
        try:
            # Se já existe, verifica se pode sobrescrever
            if os.path.exists(file_path):
                if not os.access(file_path, os.W_OK):
                    return False, f"Sem permissão para sobrescrever: {file_path}"
            else:
                # Tenta criar o arquivo
                with open(file_path, 'w') as f:
                    f.write('')
                os.remove(file_path)
        except (IOError, OSError) as e:
            return False, f"Erro ao testar escrita: {str(e)}"
            
        return True, None
        
    except Exception as e:
        return False, f"Erro ao verificar caminho: {str(e)}"

def export_clients(output_file):
    """Exporta clientes para arquivo XML com validação melhorada."""
    errors = []
    operation_details = {'arquivo_destino': output_file}
    
    try:
        # Verifica permissões
        success, error = verify_xml_path(output_file, 'w')
        if not success:
            errors.append({
                'type': 'Erro de Permissão',
                'message': error,
                'suggestion': 'Verifique se você tem permissões de escrita no diretório'
            })
            show_error_report('Exportação de Clientes', errors, operation_details)
            return False

        # Garante extensão .xml
        if not output_file.lower().endswith('.xml'):
            output_file += '.xml'

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Verifica se há clientes para exportar
            cursor.execute("SELECT COUNT(*) FROM clientes")
            total_clients = cursor.fetchone()[0]
            
            if total_clients == 0:
                errors.append({
                    'type': 'Dados Vazios',
                    'message': 'Nenhum cliente encontrado para exportar',
                    'suggestion': 'Verifique se existem clientes cadastrados'
                })
                show_error_report('Exportação de Clientes', errors, operation_details)
                return False

            # Continua com a exportação
            cursor.execute("PRAGMA table_info(clientes)")
            column_names = [col[1] for col in cursor.fetchall()]
            
            cursor.execute(f"SELECT {', '.join(column_names)} FROM clientes")
            clients = cursor.fetchall()

            # Cria estrutura XML (usando tags em português)
            root = ET.Element('clientes')
            for client in clients:
                client_elem = ET.SubElement(root, 'cliente')
                for i, field in enumerate(column_names):
                    field_elem = ET.SubElement(client_elem, field)
                    field_elem.text = str(client[i]) if client[i] is not None else ''

            # Salva o XML com tratamento de erros
            tree = ET.ElementTree(root)
            try:
                with open(output_file, 'wb') as f:
                    tree.write(f, encoding='utf-8', xml_declaration=True)
            except Exception as e:
                errors.append({
                    'type': 'Erro de Escrita',
                    'message': f"Falha ao salvar arquivo: {str(e)}",
                    'suggestion': 'Verifique permissões e espaço em disco'
                })
                show_error_report('Exportação de Clientes', errors, operation_details)
                return False

            print(f"\nExportação concluída com sucesso!")
            print(f"Total de {len(clients)} clientes exportados")
            print(f"Arquivo salvo em: {output_file}")
            return True

        except sqlite3.Error as e:
            errors.append({
                'type': 'Erro de Banco de Dados',
                'message': str(e),
                'suggestion': 'Verifique a conexão com o banco de dados'
            })
            show_error_report('Exportação de Clientes', errors, operation_details)
            return False

    except Exception as e:
        errors.append({
            'type': 'Erro Inesperado',
            'message': str(e),
            'data': {'traceback': traceback.format_exc()},
            'suggestion': 'Entre em contato com o suporte técnico'
        })
        show_error_report('Exportação de Clientes', errors, operation_details)
        return False

def test_xml_file(file_path):
    """
    Testa se um arquivo XML é válido e pode ser lido.
    Retorna (bool, str) - (sucesso, mensagem de erro)
    """
    try:
        if not os.path.exists(file_path):
            return False, f"Arquivo não encontrado: {file_path}"
        
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            # Verifica se o root tem algum elemento e se é um dos formatos aceitos
            if root.tag not in ['clients', 'clientes']:
                return False, f"A tag raiz '{root.tag}' não é suportada. Use <clients> ou <clientes>."
                
            # Procura elementos client ou cliente
            clients = root.findall('client') or root.findall('cliente')
            if len(clients) == 0:
                return False, "O arquivo XML está vazio (sem elementos client/cliente)"
            return True, None
        except ET.ParseError as e:
            return False, f"Erro ao analisar o XML: {str(e)}"
        except Exception as e:
            return False, f"Erro ao ler o arquivo XML: {str(e)}"
    except Exception as e:
        return False, f"Erro ao verificar o arquivo XML: {str(e)}"

def import_clients(xml_file):
    """Importa clientes de um arquivo XML para o banco de dados."""
    errors = []
    operation_details = {'arquivo_origem': xml_file}
    imported_count = 0
    skipped_count = 0

    try:
        # Testa se o arquivo XML é válido antes de prosseguir
        valid_xml, xml_error = test_xml_file(xml_file)
        if not valid_xml:
            errors.append({
                'type': 'Erro de XML',
                'message': xml_error,
                'suggestion': 'Verifique se o arquivo XML existe e está bem formatado'
            })
            show_error_report('Importação de Clientes', errors, operation_details)
            return False
            
        # Verifica permissões
        success, error = verify_xml_path(xml_file, 'r')
        if not success:
            errors.append({
                'type': 'Erro de Permissão',
                'message': error,
                'suggestion': 'Verifique se o arquivo existe e você tem permissões de leitura'
            })
            show_error_report('Importação de Clientes', errors, operation_details)
            return False

        # Parse XML com tratamento de erros mais detalhado
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()
            print(f"Root tag: {root.tag}")  # Debug
            
            # Verifica se a tag raiz é suportada
            if root.tag not in ['clients', 'clientes']:
                errors.append({
                    'type': 'Formato Inválido',
                    'message': f'A tag raiz do XML ({root.tag}) não é suportada',
                    'suggestion': 'O arquivo deve usar <clients> ou <clientes> como tag raiz'
                })
                show_error_report('Importação de Clientes', errors, operation_details)
                return False
                
        except Exception as e:
            errors.append({
                'type': 'Erro de Leitura',
                'message': f'Erro ao ler o arquivo: {str(e)}',
                'suggestion': 'Verifique se o arquivo não está corrompido'
            })
            show_error_report('Importação de Clientes', errors, operation_details)
            return False

        # Verifica se há elementos <client> ou <cliente> no arquivo
        client_elements = root.findall('client') or root.findall('cliente')
        print(f"Encontrados {len(client_elements)} elementos client/cliente")  # Debug
        
        if len(client_elements) == 0:
            errors.append({
                'type': 'Arquivo Inválido',
                'message': 'Não foram encontrados clientes no arquivo XML',
                'suggestion': 'Verifique se o arquivo XML está no formato correto com tags <client> ou <cliente>'
            })
            show_error_report('Importação de Clientes', errors, operation_details)
            return False

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Verifica a estrutura da tabela clientes
            cursor.execute("PRAGMA table_info(clientes)")
            table_info = cursor.fetchall()
            valid_columns = [col[1] for col in table_info]
            
            print(f"\nProcessando importação de clientes...")
            
            for client_elem in client_elements:
                try:
                    # Coleta os dados do cliente do XML
                    client_data = {}
                    
                    # Processa cada campo do cliente no XML
                    for field in valid_columns:
                        elem = client_elem.find(field)
                        if elem is not None and elem.text:
                            client_data[field] = elem.text.strip()
                        else:
                            client_data[field] = None
                    
                    # Verifica se tem pelo menos o nome do cliente
                    if not client_data.get('nome'):
                        errors.append({
                            'type': 'Dados Inválidos',
                            'message': 'Cliente sem nome encontrado no XML',
                            'suggestion': 'Todos os clientes devem ter um nome'
                        })
                        skipped_count += 1
                        continue
                    
                    # Prepara a query de inserção dinâmica
                    insert_columns = []
                    values = []
                    placeholders = []
                    
                    for field, value in client_data.items():
                        if field != 'id':  # Excluímos o ID para o banco gerar um novo
                            insert_columns.append(field)
                            values.append(value)
                            placeholders.append('?')
                    
                    # Imprime informações de depuração
                    print(f"Importando cliente: {client_data.get('nome', 'Sem nome')}")
                    
                    # Insere o cliente
                    query = f"""
                        INSERT INTO clientes ({', '.join(insert_columns)})
                        VALUES ({', '.join(placeholders)})
                    """
                    
                    cursor.execute(query, values)
                    imported_count += 1
                    
                except sqlite3.Error as e:
                    errors.append({
                        'type': 'Erro de Importação',
                        'message': f'Erro ao importar cliente: {str(e)}',
                        'data': {'cliente': client_data.get('nome', 'Desconhecido')},
                        'suggestion': 'Verifique se os dados do cliente são válidos'
                    })
                    skipped_count += 1
            
            # Confirma as alterações
            conn.commit()
            
        except sqlite3.Error as e:
            errors.append({
                'type': 'Erro de Banco de Dados',
                'message': str(e),
                'suggestion': 'Verifique a conexão com o banco de dados'
            })
            show_error_report('Importação de Clientes', errors, operation_details)
            return False
        finally:
            if 'conn' in locals() and conn:
                conn.close()

        # Atualiza detalhes da operação
        operation_details.update({
            'total_processado': imported_count + skipped_count,
            'importados': imported_count,
            'ignorados': skipped_count
        })

        if errors:
            show_error_report('Importação de Clientes', errors, operation_details)
            # Retornamos True se pelo menos um cliente foi importado com sucesso
            return imported_count > 0
            
        print(f"\nImportação concluída com sucesso!")
        print(f"Clientes importados: {imported_count}")
        if skipped_count > 0:
            print(f"Clientes ignorados devido a erros: {skipped_count}")
        
        return imported_count > 0

    except Exception as e:
        errors.append({
            'type': 'Erro Inesperado',
            'message': str(e),
            'data': {'traceback': traceback.format_exc()},
            'suggestion': 'Entre em contato com o suporte técnico'
        })
        show_error_report('Importação de Clientes', errors, operation_details)
        return False

def import_calls(xml_file):
    """Importa chamados de um arquivo XML para o banco de dados."""
    errors = []
    operation_details = {'arquivo_origem': xml_file}
    imported_count = 0
    skipped_count = 0
    andamentos_count = 0
    
    try:
        # Verifica permissões
        success, error = verify_xml_path(xml_file, 'r')
        if not success:
            errors.append({
                'type': 'Erro de Permissão',
                'message': error,
                'suggestion': 'Verifique se o arquivo existe e você tem permissões de leitura'
            })
            show_error_report('Importação de Chamados', errors, operation_details)
            return False

        # Parse XML com tratamento de erros
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()
            
            # Verifica se a tag raiz é suportada
            if root.tag not in ['calls', 'chamados']:
                errors.append({
                    'type': 'Formato Inválido',
                    'message': f'A tag raiz do XML ({root.tag}) não é suportada',
                    'suggestion': 'O arquivo deve usar <calls> ou <chamados> como tag raiz'
                })
                show_error_report('Importação de Chamados', errors, operation_details)
                return False
                
        except ET.ParseError as e:
            errors.append({
                'type': 'Erro de XML',
                'message': f'Erro ao analisar o arquivo: {str(e)}',
                'suggestion': 'Verifique se o arquivo XML está bem formatado'
            })
            show_error_report('Importação de Chamados', errors, operation_details)
            return False
            
        # Verifica se há elementos <call> ou <chamado> no arquivo
        call_elements = root.findall('call') or root.findall('chamado')
        
        if len(call_elements) == 0:
            errors.append({
                'type': 'Arquivo Inválido',
                'message': 'Não foram encontrados chamados no arquivo XML',
                'suggestion': 'Verifique se o arquivo XML está no formato correto com tags <call> ou <chamado>'
            })
            show_error_report('Importação de Chamados', errors, operation_details)
            return False
            
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Verifica a estrutura da tabela chamados
            cursor.execute("PRAGMA table_info(chamados)")
            table_info = cursor.fetchall()
            valid_columns = [col[1] for col in table_info]
            
            print(f"\nProcessando importação de chamados...")
            
            for call_elem in call_elements:
                try:
                    # Coleta todos os campos disponíveis no XML
                    call_data = {}
                    for field in valid_columns:
                        elem = call_elem.find(field)
                        if elem is not None and elem.text:
                            call_data[field] = elem.text.strip()
                        else:
                            call_data[field] = None
                    
                    # Guardamos o ID original para mapear os andamentos
                    original_id = call_elem.find('id')
                    original_id = original_id.text if original_id is not None and original_id.text else None
                    
                    # Precisamos verificar se temos ao menos os campos essenciais
                    if not call_data.get('descricao'):
                        errors.append({
                            'type': 'Dados Inválidos',
                            'message': 'Chamado sem descrição encontrado no XML',
                            'suggestion': 'Todos os chamados devem ter uma descrição'
                        })
                        skipped_count += 1
                        continue
                        
                    # Prepara e executa a query de inserção
                    insert_columns = []
                    values = []
                    placeholders = []
                    
                    for field, value in call_data.items():
                        if field != 'id':  # Não inserimos o ID, deixamos o banco gerar
                            insert_columns.append(field)
                            values.append(value)
                            placeholders.append('?')
                    
                    # Imprime informações de importação
                    descr_preview = call_data.get('descricao', '')[:30]
                    if len(call_data.get('descricao', '')) > 30:
                        descr_preview += "..."
                    print(f"Importando chamado: {descr_preview}")
                    
                    query = f"""
                        INSERT INTO chamados ({', '.join(insert_columns)})
                        VALUES ({', '.join(placeholders)})
                    """
                    
                    cursor.execute(query, values)
                    new_call_id = cursor.lastrowid
                    
                    # Importa os andamentos, se existirem
                    andamentos_elem = call_elem.find('andamentos')
                    if andamentos_elem is not None:
                        for andamento_elem in andamentos_elem.findall('andamento'):
                            try:
                                data_hora = andamento_elem.find('data_hora')
                                texto = andamento_elem.find('texto')
                                
                                if data_hora is not None and data_hora.text and texto is not None and texto.text:
                                    # Insere o andamento com o ID do novo chamado
                                    cursor.execute("""
                                        INSERT INTO chamado_andamentos (chamado_id, data_hora, texto)
                                        VALUES (?, ?, ?)
                                    """, (new_call_id, data_hora.text, texto.text))
                                    andamentos_count += 1
                            except sqlite3.Error as e:
                                errors.append({
                                    'type': 'Erro de Importação',
                                    'message': f'Erro ao importar andamento: {str(e)}',
                                    'suggestion': 'Verifique os dados do andamento'
                                })
                    
                    imported_count += 1
                    
                except sqlite3.Error as e:
                    errors.append({
                        'type': 'Erro de Importação',
                        'message': f'Erro ao importar chamado: {str(e)}',
                        'data': {'descrição': call_data.get('descricao', '')[:50]},
                        'suggestion': 'Verifique se os dados do chamado são válidos'
                    })
                    skipped_count += 1
            
            # Confirma as alterações
            conn.commit()
            
        except sqlite3.Error as e:
            errors.append({
                'type': 'Erro de Banco de Dados',
                'message': str(e),
                'suggestion': 'Verifique a conexão com o banco de dados'
            })
            show_error_report('Importação de Chamados', errors, operation_details)
            return False
        finally:
            if 'conn' in locals() and conn:
                conn.close()
                
        # Atualiza detalhes da operação
        operation_details.update({
            'total_processado': imported_count + skipped_count,
            'importados': imported_count,
            'andamentos_importados': andamentos_count,
            'ignorados': skipped_count
        })

        if errors:
            show_error_report('Importação de Chamados', errors, operation_details)
            # Retornamos True se pelo menos um chamado foi importado com sucesso
            return imported_count > 0
            
        print(f"\nImportação concluída com sucesso!")
        print(f"Chamados importados: {imported_count}")
        print(f"Andamentos importados: {andamentos_count}")
        if skipped_count > 0:
            print(f"Chamados ignorados devido a erros: {skipped_count}")
        
        return imported_count > 0
            
    except Exception as e:
        errors.append({
            'type': 'Erro Inesperado',
            'message': str(e),
            'data': {'traceback': traceback.format_exc()},
            'suggestion': 'Entre em contato com o suporte técnico'
        })
        show_error_report('Importação de Chamados', errors, operation_details)
        return False

def export_calls(output_file, status=None):
    """Exporta chamados para um arquivo XML, com filtragem opcional por status."""
    try:
        # Validar e ajustar o caminho do arquivo
        if not output_file or output_file.strip() in ['c:/', 'c:', '/', '\\']:
            print("\nErro: Caminho inválido!")
            print("Por favor, especifique um caminho completo incluindo o nome do arquivo.")
            print("Exemplo: c:/HelpHub/export/chamados/chamados.xml")
            return False
            
        if not output_file.lower().endswith('.xml'):
            output_file += '.xml'

        # Criar diretórios e verificar permissões
        try:
            dir_path = os.path.dirname(output_file)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
                
            with open(output_file, 'w', encoding='utf-8') as test_file:
                pass
        except Exception as e:
            print(f"\nErro ao preparar o arquivo: {e}")
            return False

        # Conexão com o banco
        conn = get_db_connection()
        cursor = conn.cursor()

        # Verifica a estrutura da tabela chamados
        cursor.execute("PRAGMA table_info(chamados)")
        table_info = cursor.fetchall()
        column_names = [col[1] for col in table_info]
        
        # Constrói a query dinamicamente
        query = f"SELECT {', '.join(column_names)} FROM chamados"
        
        # Adiciona filtro de status se especificado
        if status:
            query += " WHERE status = ?"
            cursor.execute(query, (status,))
        else:
            cursor.execute(query)

        calls = cursor.fetchall()

        # Cria a estrutura do XML (usando tags em português)
        root = ET.Element('chamados')
        
        total = 0
        for call in calls:
            call_elem = ET.SubElement(root, 'chamado')
            
            # Adiciona todos os campos do chamado
            for field_idx, field in enumerate(column_names):
                sub = ET.SubElement(call_elem, field)
                sub.text = str(call[field_idx]) if call[field_idx] is not None else ''

            # Busca e adiciona os andamentos do chamado
            cursor.execute("""
                SELECT id, data_hora, texto
                FROM chamado_andamentos
                WHERE chamado_id = ?
                ORDER BY data_hora
            """, (call[0],))
            
            andamentos = cursor.fetchall()
            andamentos_elem = ET.SubElement(call_elem, 'andamentos')
            
            for andamento in andamentos:
                andamento_elem = ET.SubElement(andamentos_elem, 'andamento')
                andamento_fields = ['id', 'data_hora', 'texto']
                
                for field_idx, field in enumerate(andamento_fields):
                    sub = ET.SubElement(andamento_elem, field)
                    sub.text = str(andamento[field_idx]) if andamento[field_idx] is not None else ''
            
            total += 1

        # Salva o XML
        tree = ET.ElementTree(root)
        tree.write(output_file, encoding='utf-8', xml_declaration=True)
        
        conn.close()
        print(f"\nExportação de chamados concluída com sucesso!")
        print(f"Total de chamados exportados: {total}")
        print(f"Arquivo salvo em: {output_file}")
        return True
        
    except Exception as e:
        print(f"\nErro durante a exportação de chamados: {e}")
        return False

def import_calls(xml_file):
    """Importa chamados de um arquivo XML para o banco de dados."""
    errors = []
    operation_details = {'arquivo_origem': xml_file}
    imported_count = 0
    skipped_count = 0
    andamentos_count = 0
    
    try:
        # Verifica permissões
        success, error = verify_xml_path(xml_file, 'r')
        if not success:
            errors.append({
                'type': 'Erro de Permissão',
                'message': error,
                'suggestion': 'Verifique se o arquivo existe e você tem permissões de leitura'
            })
            show_error_report('Importação de Chamados', errors, operation_details)
            return False

        # Parse XML com tratamento de erros
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()
            
            # Verifica se a tag raiz é suportada
            if root.tag not in ['calls', 'chamados']:
                errors.append({
                    'type': 'Formato Inválido',
                    'message': f'A tag raiz do XML ({root.tag}) não é suportada',
                    'suggestion': 'O arquivo deve usar <calls> ou <chamados> como tag raiz'
                })
                show_error_report('Importação de Chamados', errors, operation_details)
                return False
                
        except ET.ParseError as e:
            errors.append({
                'type': 'Erro de XML',
                'message': f'Erro ao analisar o arquivo: {str(e)}',
                'suggestion': 'Verifique se o arquivo XML está bem formatado'
            })
            show_error_report('Importação de Chamados', errors, operation_details)
            return False
            
        # Verifica se há elementos <call> ou <chamado> no arquivo
        call_elements = root.findall('call') or root.findall('chamado')
        
        if len(call_elements) == 0:
            errors.append({
                'type': 'Arquivo Inválido',
                'message': 'Não foram encontrados chamados no arquivo XML',
                'suggestion': 'Verifique se o arquivo XML está no formato correto com tags <call> ou <chamado>'
            })
            show_error_report('Importação de Chamados', errors, operation_details)
            return False
            
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Verifica a estrutura da tabela chamados
            cursor.execute("PRAGMA table_info(chamados)")
            table_info = cursor.fetchall()
            valid_columns = [col[1] for col in table_info]
            
            print(f"\nProcessando importação de chamados...")
            
            for call_elem in call_elements:
                try:
                    # Coleta todos os campos disponíveis no XML
                    call_data = {}
                    for field in valid_columns:
                        elem = call_elem.find(field)
                        if elem is not None and elem.text:
                            call_data[field] = elem.text.strip()
                        else:
                            call_data[field] = None
                    
                    # Guardamos o ID original para mapear os andamentos
                    original_id = call_elem.find('id')
                    original_id = original_id.text if original_id is not None and original_id.text else None
                    
                    # Precisamos verificar se temos ao menos os campos essenciais
                    if not call_data.get('descricao'):
                        errors.append({
                            'type': 'Dados Inválidos',
                            'message': 'Chamado sem descrição encontrado no XML',
                            'suggestion': 'Todos os chamados devem ter uma descrição'
                        })
                        skipped_count += 1
                        continue
                        
                    # Prepara e executa a query de inserção
                    insert_columns = []
                    values = []
                    placeholders = []
                    
                    for field, value in call_data.items():
                        if field != 'id':  # Não inserimos o ID, deixamos o banco gerar
                            insert_columns.append(field)
                            values.append(value)
                            placeholders.append('?')
                    
                    # Imprime informações de importação
                    descr_preview = call_data.get('descricao', '')[:30]
                    if len(call_data.get('descricao', '')) > 30:
                        descr_preview += "..."
                    print(f"Importando chamado: {descr_preview}")
                    
                    query = f"""
                        INSERT INTO chamados ({', '.join(insert_columns)})
                        VALUES ({', '.join(placeholders)})
                    """
                    
                    cursor.execute(query, values)
                    new_call_id = cursor.lastrowid
                    
                    # Importa os andamentos, se existirem
                    andamentos_elem = call_elem.find('andamentos')
                    if andamentos_elem is not None:
                        for andamento_elem in andamentos_elem.findall('andamento'):
                            try:
                                data_hora = andamento_elem.find('data_hora')
                                texto = andamento_elem.find('texto')
                                
                                if data_hora is not None and data_hora.text and texto is not None and texto.text:
                                    # Insere o andamento com o ID do novo chamado
                                    cursor.execute("""
                                        INSERT INTO chamado_andamentos (chamado_id, data_hora, texto)
                                        VALUES (?, ?, ?)
                                    """, (new_call_id, data_hora.text, texto.text))
                                    andamentos_count += 1
                            except sqlite3.Error as e:
                                errors.append({
                                    'type': 'Erro de Importação',
                                    'message': f'Erro ao importar andamento: {str(e)}',
                                    'suggestion': 'Verifique os dados do andamento'
                                })
                    
                    imported_count += 1
                    
                except sqlite3.Error as e:
                    errors.append({
                        'type': 'Erro de Importação',
                        'message': f'Erro ao importar chamado: {str(e)}',
                        'data': {'descrição': call_data.get('descricao', '')[:50]},
                        'suggestion': 'Verifique se os dados do chamado são válidos'
                    })
                    skipped_count += 1
            
            # Confirma as alterações
            conn.commit()
            
        except sqlite3.Error as e:
            errors.append({
                'type': 'Erro de Banco de Dados',
                'message': str(e),
                'suggestion': 'Verifique a conexão com o banco de dados'
            })
            show_error_report('Importação de Chamados', errors, operation_details)
            return False
        finally:
            if 'conn' in locals() and conn:
                conn.close()
                
        # Atualiza detalhes da operação
        operation_details.update({
            'total_processado': imported_count + skipped_count,
            'importados': imported_count,
            'andamentos_importados': andamentos_count,
            'ignorados': skipped_count
        })

        if errors:
            show_error_report('Importação de Chamados', errors, operation_details)
            # Retornamos True se pelo menos um chamado foi importado com sucesso
            return imported_count > 0
            
        print(f"\nImportação concluída com sucesso!")
        print(f"Chamados importados: {imported_count}")
        print(f"Andamentos importados: {andamentos_count}")
        if skipped_count > 0:
            print(f"Chamados ignorados devido a erros: {skipped_count}")
        
        return imported_count > 0
            
    except Exception as e:
        errors.append({
            'type': 'Erro Inesperado',
            'message': str(e),
            'data': {'traceback': traceback.format_exc()},
            'suggestion': 'Entre em contato com o suporte técnico'
        })
        show_error_report('Importação de Chamados', errors, operation_details)
        return False

def navigate_interactive(start_path, file_ext=None, title="Navegador de Arquivos"):
    """
    Sistema de navegação interativa melhorado com suporte a teclado.
    
    Args:
        start_path (str): Diretório inicial
        file_ext (str, opcional): Extensão de arquivo a ser destacada (.db, .xml)
        title (str): Título a ser exibido no navegador
        
    Returns:
        str: Caminho do arquivo selecionado ou None se cancelado
    """
    current_path = os.path.abspath(start_path)
    selected_idx = 0
    items_per_page = 15
    page_offset = 0
    
    while True:
        # Limpa a tela
        os.system('cls' if os.name == 'nt' else 'clear')
        
        # Cabeçalho
        print("\n┌─────────────────────────────────────────────────────────────┐")
        print(f"│ {title:<59} │")
        print("└─────────────────────────────────────────────────────────────┘")
        
        # Mostra o caminho atual
        print(f"\nPasta atual: {current_path}")
        
        # Instruções
        print("\nUse as setas ↑ ↓ para navegar, Enter para selecionar,")
        print("Backspace para voltar, Esc para cancelar")
        
        try:
            # Lista os itens do diretório atual
            items = os.listdir(current_path)
        except PermissionError:
            print("\nSem permissão para acessar este diretório.")
            print("Voltando ao diretório anterior...")
            current_path = os.path.dirname(current_path)
            time.sleep(1)
            continue
        except Exception as e:
            print(f"\nErro ao listar diretório: {e}")
            print("Voltando ao diretório anterior...")
            current_path = os.path.dirname(current_path)
            time.sleep(1)
            continue
        
        # Separa em pastas e arquivos
        directories = sorted([item for item in items if os.path.isdir(os.path.join(current_path, item))])
        if file_ext:
            # Se um tipo de arquivo específico foi fornecido, separa em matching e outros
            matching_files = sorted([item for item in items if os.path.isfile(os.path.join(current_path, item)) 
                                   and item.lower().endswith(file_ext.lower())])
            other_files = sorted([item for item in items if os.path.isfile(os.path.join(current_path, item)) 
                                and not item.lower().endswith(file_ext.lower())])
            files = matching_files + other_files
        else:
            files = sorted([item for item in items if os.path.isfile(os.path.join(current_path, item))])
            
        all_items = directories + files
        
        # Verifica se há itens para mostrar
        if not all_items:
            print("\nDiretório vazio!")
            print("Pressione Backspace para voltar...")
            key = getch()
            if key == '\x08' or key == '\x7f':  # Backspace key
                parent = os.path.dirname(current_path)
                if parent != current_path:  # Evita loop na raiz
                    current_path = parent
            continue
        
        # Paginação
        total_items = len(all_items)
        max_pages = (total_items + items_per_page - 1) // items_per_page
        current_page = page_offset // items_per_page + 1
        
        # Ajuste do índice selecionado para a página atual
        if selected_idx < page_offset:
            page_offset = (selected_idx // items_per_page) * items_per_page
        elif selected_idx >= page_offset + items_per_page:
            page_offset = (selected_idx // items_per_page) * items_per_page
            
        visible_items = all_items[page_offset:page_offset+items_per_page]
        
        # Exibe cabeçalho da listagem
        print("\n  NOME                                                 TIPO")
        print("  ─────────────────────────────────────────────────────────")
        
        # Exibe os itens com ícones e formatação
        for i, item in enumerate(visible_items):
            idx = i + page_offset
            is_dir = idx < len(directories)
            is_matching = not is_dir and file_ext and item.lower().endswith(file_ext.lower())
            
            # Define ícone e tipo
            if is_dir:
                icon = "📁"
                file_type = "Pasta"
            elif is_matching:
                icon = "📄"
                file_type = f"Arquivo {file_ext.upper()}"
            else:
                icon = "📝"
                file_type = "Arquivo"
            
            # Destaca o item selecionado
            if idx == selected_idx:
                print(f"→ {icon} {item[:40]:<40} {file_type}")
            else:
                print(f"  {icon} {item[:40]:<40} {file_type}")
        
        # Mostra informações de paginação
        if max_pages > 1:
            print(f"\nPágina {current_page} de {max_pages} | {total_items} itens")
        
        # Lê entrada do teclado
        key = getch()
        
        # Processa a tecla pressionada
        if key == '\r' or key == '\n':  # Enter
            selected_item = all_items[selected_idx]
            full_path = os.path.join(current_path, selected_item)
            
            if os.path.isdir(full_path):
                # Navega para o diretório selecionado
                current_path = full_path
                selected_idx = 0
                page_offset = 0
            else:
                # Verifica se o arquivo selecionado tem a extensão correta
                if not file_ext or selected_item.lower().endswith(file_ext.lower()):
                    return full_path
                else:
                    print(f"\nApenas arquivos {file_ext.upper()} podem ser selecionados.")
                    time.sleep(1)
                    
        elif key == '\x08' or key == '\x7f':  # Backspace
            parent = os.path.dirname(current_path)
            if parent != current_path:  # Evita loop na raiz
                current_path = parent
                selected_idx = 0
                page_offset = 0
                
        elif key == '\x1b':  # Escape
            print("\nOperação cancelada pelo usuário")
            return None
            
        elif key in ['H', 'A', 'w']:  # Seta para cima ou W
            selected_idx = max(0, selected_idx - 1)
            
        elif key in ['P', 'B', 's']:  # Seta para baixo ou S
            selected_idx = min(len(all_items) - 1, selected_idx + 1)
            
        elif key in ['K', 'D', 'a']:  # Seta para esquerda ou A
            page_offset = max(0, page_offset - items_per_page)
            selected_idx = page_offset
            
        elif key in ['M', 'C', 'd']:  # Seta para direita ou D
            new_page_offset = min(total_items - 1, page_offset + items_per_page)
            if new_page_offset != page_offset:
                page_offset = new_page_offset
                selected_idx = page_offset

def ensure_database_exists():
    """Verifica se o arquivo de banco de dados existe, ou solicita navegação para selecioná-lo."""
    global DATABASE
    
    if os.path.isfile(DATABASE):
        return True
        
    print(f"\nDatabase não encontrado em: {DATABASE}")
    print("\nPressione Enter para navegar e selecionar o arquivo database.db...")
    input()
    
    selected = navigate_interactive(
        os.getcwd(), 
        '.db', 
        "Selecione o arquivo database.db"    
    )
    
    if selected and os.path.basename(selected).lower() == 'database.db':
        DATABASE = selected
        print(f"\nDatabase configurado para: {DATABASE}")
        return True
    else:
        print("\nArquivo database.db não selecionado. Encerrando.")
        return False

def get_xml_file(mode="input"):
    """
    Interface para selecionar arquivo XML para importação ou exportação.
    
    Args:
        mode (str): "input" para importação, "output" para exportação
    """
    action = "importar de" if mode == "input" else "exportar para"
    default_path = "c:/HelpHub/export/clientes/clientes.xml"
    
    print(f"\nEscolha onde {action} o arquivo XML:")
    print(f"  1. Usar o caminho padrão: {default_path}")
    print("  2. Navegar pelo sistema de arquivos (modo interativo)")
    print("  3. Digitar o caminho manualmente")
    
    opcao = input("\nDigite o número da opção desejada: ").strip()

    if opcao == "1":
        if mode == "output" or os.path.exists(default_path):
            return default_path
        else:
            print("\nArquivo padrão não encontrado. Redirecionando para navegação interativa...")
            time.sleep(1.5)
            opcao = "2"
    
    if opcao == "2":
        title = "Selecione onde salvar o arquivo XML" if mode == "output" else "Selecione o arquivo XML para importar"
        start_path = os.path.dirname(default_path) if os.path.exists(os.path.dirname(default_path)) else os.getcwd()
        
        selected = navigate_interactive(start_path, '.xml', title)
        if selected:
            return selected
        else:
            return None
            
    elif opcao == "3":
        path = input(f"\nDigite o caminho completo para {action} o arquivo XML: ").strip()
        if mode == "output" or os.path.exists(path):
            return path
        else:
            print(f"\nArquivo não encontrado: {path}")
            return None
            
    else:
        print("\nOpção inválida.")
        return None

def main():
    """Função principal que executa o menu interativo."""
    # Verificar se o banco de dados existe antes de continuar
    if not ensure_database_exists():
        sys.exit(1)
    
    # Interface gráfica do menu principal
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        
        # Cabeçalho do programa
        print("\n┌─────────────────────────────────────────────────────────────┐")
        print("│               HelpHub - Importação e Exportação              │")
        print("└─────────────────────────────────────────────────────────────┘")
        
        print(f"\nBanco de dados conectado: {DATABASE}")
        print("\nEscolha uma opção:")
        print("  1. Exportar clientes para XML")
        print("  2. Importar clientes de XML")
        print("  3. Exportar chamados para XML")
        print("  4. Importar chamados de XML")
        print("  5. Sair")
        
        opcao = input("\nDigite o número da opção desejada: ").strip()

        if opcao == "1":
            export_clients_menu()
        elif opcao == "2":
            import_clients_menu()
        elif opcao == "3":
            export_calls_menu()
        elif opcao == "4":
            import_calls_menu()
        elif opcao == "5":
            print("\nEncerrando o programa...")
            break
        else:
            print("\nOpção inválida. Pressione qualquer tecla para continuar...")
            getch()

def export_clients_menu():
    """Menu para exportação de clientes."""
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print("\n┌─────────────────────────────────────────────────────────────┐")
        print("│                   Exportação de Clientes                    │")
        print("└─────────────────────────────────────────────────────────────┘")
        
        print("\nEscolha o destino do arquivo XML:")
        print("  1. Usar caminho padrão (c:/HelpHub/export/clientes/clientes.xml)")
        print("  2. Navegar pelo sistema de arquivos (modo interativo)")
        print("  3. Digitar o caminho manualmente")
        print("  4. Voltar ao menu principal")
        
        opcao = input("\nDigite o número da opção desejada: ").strip()
        
        if opcao == "1":
            output = "c:/HelpHub/export/clientes/clientes.xml"
            if export_clients(output):
                print("\nPressione qualquer tecla para continuar...")
                getch()
                return
        elif opcao == "2":
            title = "Selecione onde salvar o arquivo XML de clientes"
            start_path = os.path.dirname("c:/HelpHub/export/clientes/") if os.path.exists("c:/HelpHub/export/clientes/") else os.getcwd()
            
            output = navigate_interactive(start_path, '.xml', title)
            if output:
                if export_clients(output):
                    print("\nPressione qualquer tecla para continuar...")
                    getch()
                    return
        elif opcao == "3":
            print("\nInforme o caminho completo para o arquivo XML.")
            print("Exemplo: c:/MeusProjetos/backup/clientes.xml")
            output = input("\nCaminho: ").strip()
            if export_clients(output):
                print("\nPressione qualquer tecla para continuar...")
                getch()
                return
        elif opcao == "4":
            return
        else:
            print("\nOpção inválida. Pressione qualquer tecla para continuar...")
            getch()

def import_clients_menu():
    """Menu para importação de clientes."""
    os.system('cls' if os.name == 'nt' else 'clear')
    print("\n┌─────────────────────────────────────────────────────────────┐")
    print("│                   Importação de Clientes                    │")
    print("└─────────────────────────────────────────────────────────────┘")
    
    xml_file = get_xml_file("input")
    if xml_file:
        if import_clients(xml_file):
            print("\nPressione qualquer tecla para continuar...")
            getch()

def export_calls_menu():
    """Menu para exportação de chamados."""
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print("\n┌─────────────────────────────────────────────────────────────┐")
        print("│                   Exportação de Chamados                    │")
        print("└─────────────────────────────────────────────────────────────┘")
        
        print("\nEscolha o tipo de chamados para exportar:")
        print("  1. Todos os chamados")
        print("  2. Apenas chamados abertos")
        print("  3. Apenas chamados finalizados")
        print("  4. Voltar ao menu principal")
        
        opcao = input("\nDigite o número da opção desejada: ").strip()
        
        if opcao == "4":
            return
        
        status = None
        if opcao == "2":
            status = "Aberto"
            status_text = "abertos"
        elif opcao == "3":
            status = "Finalizado"
            status_text = "finalizados"
        elif opcao == "1":
            status_text = ""
        else:
            print("\nOpção inválida. Pressione qualquer tecla para continuar...")
            getch()
            continue
            
        # Submenu para escolher o destino do arquivo
        os.system('cls' if os.name == 'nt' else 'clear')
        print("\n┌─────────────────────────────────────────────────────────────┐")
        print(f"│              Exportação de Chamados {status_text:<18} │")
        print("└─────────────────────────────────────────────────────────────┘")
        
        print("\nEscolha o destino do arquivo XML:")
        print("  1. Usar caminho padrão (c:/HelpHub/export/chamados/chamados.xml)")
        print("  2. Navegar pelo sistema de arquivos (modo interativo)")
        print("  3. Digitar o caminho manualmente")
        
        path_opcao = input("\nDigite o número da opção desejada: ").strip()
        
        if path_opcao == "1":
            output = "c:/HelpHub/export/chamados/chamados.xml"
            if export_calls(output, status):
                print("\nPressione qualquer tecla para continuar...")
                getch()
                return
        elif path_opcao == "2":
            title = "Selecione onde salvar o arquivo XML de chamados"
            start_path = os.path.dirname("c:/HelpHub/export/chamados/") if os.path.exists("c:/HelpHub/export/chamados/") else os.getcwd()
            
            output = navigate_interactive(start_path, '.xml', title)
            if output:
                if export_calls(output, status):
                    print("\nPressione qualquer tecla para continuar...")
                    getch()
                    return
        elif path_opcao == "3":
            print("\nInforme o caminho completo para o arquivo XML.")
            print("Exemplo: c:/MeusProjetos/backup/chamados.xml")
            output = input("\nCaminho: ").strip()
            if export_calls(output, status):
                print("\nPressione qualquer tecla para continuar...")
                getch()
                return

def import_calls_menu():
    """Menu para importação de chamados."""
    os.system('cls' if os.name == 'nt' else 'clear')
    print("\n┌─────────────────────────────────────────────────────────────┐")
    print("│                   Importação de Chamados                    │")
    print("└─────────────────────────────────────────────────────────────┘")
    
    xml_file = get_xml_file("input")
    if xml_file:
        if import_calls(xml_file):
            print("\nPressione qualquer tecla para continuar...")
            getch()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Importação e Exportação de Dados do HelpHub")
    parser.add_argument('--db', help='Caminho para o arquivo database.db', default=DATABASE)
    parser.add_argument('--export-clients', help='Exportar clientes para arquivo XML')
    parser.add_argument('--import-clients', help='Importar clientes de arquivo XML')
    parser.add_argument('--export-calls', help='Exportar chamados para arquivo XML')
    parser.add_argument('--import-calls', help='Importar chamados de arquivo XML')
    parser.add_argument('--calls-status', help='Filtro de status para exportação de chamados (Aberto/Finalizado)')
    
    args = parser.parse_args()
    
    # Atualiza a localização do database
    if args.db:
        DATABASE = args.db
    
    # Modo de linha de comando com argumentos específicos
    if args.export_clients:
        if ensure_database_exists():
            export_clients(args.export_clients)
        sys.exit(0)
    elif args.import_clients:
        if ensure_database_exists():
            import_clients(args.import_clients)
        sys.exit(0)
    elif args.export_calls:
        if ensure_database_exists():
            export_calls(args.export_calls, args.calls_status)
        sys.exit(0)
    elif args.import_calls:
        if ensure_database_exists():
            import_calls(args.import_calls)
        sys.exit(0)
    
    # Sem argumentos específicos, inicia o menu interativo
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nPrograma encerrado pelo usuário.")
        sys.exit(0)
    except Exception as e:
        print(f"\nErro inesperado: {e}")
        input("\nPressione Enter para sair...")
        sys.exit(1)
