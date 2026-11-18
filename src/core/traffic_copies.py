"""Endereços das cópias de um trecho reproduzidas ao mesmo tempo na rede emulada.

A cópia 1 é o trecho sem alteração. Cada cópia seguinte troca cada endereço IPv4 do trecho por um endereço próprio,
reservado à cópia, e mantém o restante de cada pacote. Assim, os fluxos de cópias diferentes nunca se misturam, e
cada fluxo de uma cópia tem as mesmas entradas do fluxo correspondente do trecho.

Só a biblioteca padrão é usada, porque o script de emulação roda com o Python do sistema."""

import hashlib
import ipaddress

# Bloco de endereços das cópias (RFC 6598). Ele não aparece no tráfego do CIC-IDS2017, e a preparação confere isso.
COPY_NETWORK = ipaddress.IPv4Network("100.64.0.0/10")
# Endereços reservados a cada cópia. O trecho precisa ter no máximo esse número de endereços IPv4.
COPY_BLOCK = 4096
MAX_COPIES = 1 + COPY_NETWORK.num_addresses // COPY_BLOCK
# Maior argumento que o Linux aceita num exec (MAX_ARG_STRLEN).
MAX_ARGUMENT_BYTES = 131072


def check_addresses(addresses: list[str]) -> None:
    """Confere que os endereços do trecho cabem no bloco de cada cópia e não colidem com os das cópias."""
    if len(addresses) != len(set(addresses)):
        raise ValueError("Endereços repetidos na lista do trecho.")
    if len(addresses) > COPY_BLOCK:
        raise ValueError(f"O trecho tem {len(addresses)} endereços IPv4, mais que os {COPY_BLOCK} de cada cópia.")
    inside = [address for address in addresses if ipaddress.IPv4Address(address) in COPY_NETWORK]
    if inside:
        raise ValueError(f"O trecho já usa endereços do bloco das cópias: {inside[:5]}.")


def copy_address(index: int, copy: int) -> str:
    """Endereço que substitui, na cópia dada, o endereço de posição `index` na lista do trecho."""
    if not 2 <= copy <= MAX_COPIES or not 0 <= index < COPY_BLOCK:
        raise ValueError(f"Cópia {copy} ou posição {index} fora do bloco das cópias.")
    return str(COPY_NETWORK.network_address + (copy - 2) * COPY_BLOCK + index)


def address_map(addresses: list[str], copy: int) -> dict[str, str]:
    """Troca de endereços de uma cópia. A cópia 1 não troca nenhum."""
    check_addresses(addresses)
    if copy == 1:
        return {}
    return {address: copy_address(index, copy) for index, address in enumerate(addresses)}


def pnat_argument(addresses: list[str], copy: int) -> str | None:
    """Opção --pnat do tcpreplay-edit para uma cópia, um par /32 por endereço, na ordem da lista.

    O tcpreplay-edit percorre os pares em ordem a cada pacote. A lista do trecho vem ordenada pelo número de
    pacotes, para que os endereços mais frequentes sejam encontrados primeiro."""
    mapping = address_map(addresses, copy)
    if not mapping:
        return None
    argument = "--pnat=" + ",".join(f"{source}/32:{target}/32" for source, target in mapping.items())
    if len(argument.encode()) >= MAX_ARGUMENT_BYTES:
        raise ValueError("A lista de endereços não cabe num argumento do tcpreplay-edit.")
    return argument


def argument_digest(argument: str | None) -> str | None:
    return None if argument is None else hashlib.sha256(argument.encode()).hexdigest()


def copy_of(address: str, positions: dict[str, int], addresses: list[str]) -> tuple[int, str] | None:
    """Cópia a que um endereço pertence e o endereço original correspondente. Fora do trecho, devolve None."""
    if address in positions:
        return 1, address
    try:
        parsed = ipaddress.IPv4Address(address)
    except ValueError:
        return None
    if parsed not in COPY_NETWORK:
        return None
    offset = int(parsed) - int(COPY_NETWORK.network_address)
    copy, index = 2 + offset // COPY_BLOCK, offset % COPY_BLOCK
    if index >= len(addresses):
        return None
    return copy, addresses[index]
