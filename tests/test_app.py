from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def load():
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception, at.exception
    return at


def textos(at):
    return " ".join(m.value for c in at.chat_message for m in c.markdown)


def test_formulario_cidade_unica_aceita_nomes():
    at = load()
    at.sidebar.button[0].click().run()          # padrão: "São Paulo" -> "Lisboa"
    assert not at.exception, at.exception
    t = textos(at)
    assert "São Paulo (GRU)" in t and "Lisboa (LIS)" in t and "Achei" in t
    assert len(at.dataframe) == 1                # tabela completa no expander


def test_formulario_por_regiao():
    at = load()
    at.sidebar.radio[0].set_value("Região").run()
    at.sidebar.slider[0].set_value(0)
    at.sidebar.button[0].click().run()
    assert not at.exception, at.exception
    t = textos(at)
    assert "Europa (11 destinos)" in t and "Outros destinos" in t


def test_chat_por_regiao():
    at = load()
    at.chat_input[0].set_value("GRU para qualquer cidade da Europa em 10/12, 10 dias").run()
    assert not at.exception, at.exception
    assert "Europa" in textos(at)
    notas = " ".join(c.value for m in at.chat_message for c in m.caption)
    assert "interpretado por: regras" in notas


def test_botao_de_exemplo_dispara_busca_e_some():
    at = load()
    at.button[0].click().run()
    assert not at.exception, at.exception
    assert "Achei" in textos(at)
    at.run()
    assert not [b for b in at.button if b.label.startswith("São Paulo para")]


def test_chat_pedido_incompleto_mostra_erro_sem_quebrar():
    at = load()
    at.chat_input[0].set_value("quero viajar").run()
    assert not at.exception, at.exception
    assert len(at.error) == 1
    assert len(at.session_state.history) == 2    # pergunta + resposta de erro


def test_criar_monitoramento_pela_interface():
    from flight_agent import watch
    at = load()
    at.sidebar.button[0].click().run()
    criar = [b for b in at.button if b.label == "Criar monitoramento"]
    criar[0].click().run()
    assert not at.exception, at.exception
    items = watch.load_watches()
    assert len(items) == 1 and items[0]["query"]["dests"] == ["LIS"]
    assert any("Monitorando" in s.value for s in at.success)
    assert "Monitoramentos (1)" in " ".join(e.label for e in at.sidebar.expander)
