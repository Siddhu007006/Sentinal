"""
Infrastructure layer.

Concrete implementations of everything external: database access,
object storage, queues, AI provider clients, email, logging, and
configuration loading. Every subfolder is an adapter that translates
between the Domain's vocabulary and a specific external technology.

See: 06-Repository-Structure.md §7.
"""
