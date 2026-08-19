import os
import unittest
from unittest.mock import MagicMock, patch

# Configura variáveis de ambiente de teste antes de importar o main
os.environ["SCORES_FILE_PATH"] = "test_scores.json"

import backend.main as main

class TestTetrisBackend(unittest.TestCase):
    def setUp(self):
        # Limpar arquivo de teste local se existir
        if os.path.exists("test_scores.json"):
            try:
                os.remove("test_scores.json")
            except OSError:
                pass

    def tearDown(self):
        # Limpar arquivo de teste local se existir
        if os.path.exists("test_scores.json"):
            try:
                os.remove("test_scores.json")
            except OSError:
                pass

    def test_local_fallback_load_default(self):
        """Testa se carrega os scores padrão se o arquivo não existir."""
        scores = main.load_scores_local()
        self.assertEqual(len(scores), 5)
        self.assertEqual(scores[0]["name"], "NEON_MASTER")

    def test_local_fallback_save_and_load(self):
        """Testa se salva e carrega corretamente localmente."""
        test_data = [{"name": "TEST_PLAYER", "score": 999999, "level": 10, "lines": 100}]
        main.save_scores_local(test_data)
        scores = main.load_scores_local()
        self.assertEqual(len(scores), 1)
        self.assertEqual(scores[0]["name"], "TEST_PLAYER")

    @patch("backend.main.db")
    def test_firestore_load_empty_populates_defaults(self, mock_db):
        """Testa se popula valores padrão no Firestore se a coleção estiver vazia."""
        # Configurar mock de db no módulo
        main.db = mock_db
        
        # Mocar coleções e consultas do Firestore
        mock_col = MagicMock()
        mock_query = MagicMock()
        mock_db.collection.return_value = mock_col
        mock_col.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        
        # Primeira chamada de stream() retorna lista vazia (coleção sem nada)
        # Segunda chamada (após popular) retorna o documento mocado
        mock_doc = MagicMock()
        mock_doc.to_dict.return_value = {"name": "MOCK_CHAMP", "score": 120000}
        
        mock_query.stream.side_effect = [[], [mock_doc]]
        
        # Chamar a função de carregamento do Firestore
        scores = main.load_scores_from_firestore()
        
        # Verificar se o batch foi criado para popular os dados padrões
        mock_db.batch.assert_called_once()
        self.assertEqual(len(scores), 1)
        self.assertEqual(scores[0]["name"], "MOCK_CHAMP")

    @patch("backend.main.db")
    def test_firestore_save_score(self, mock_db):
        """Testa o salvamento de um score no Firestore."""
        main.db = mock_db
        mock_col = MagicMock()
        mock_db.collection.return_value = mock_col
        
        test_entry = {"name": "NEW_HERO", "score": 150000, "level": 12, "lines": 120}
        main.save_score_to_firestore(test_entry)
        
        # Verifica se o documento foi adicionado na coleção do Firestore
        mock_col.add.assert_called_once_with(test_entry)

if __name__ == "__main__":
    unittest.main()