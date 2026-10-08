"""Ponto de extensão para alertas. Hoje imprime na tela; troque por Telegram, e-mail, etc."""


def notify(message: str) -> None:
    print(f"\n🔔 ALERTA: {message}")
