# ===== apps/exchanges/views.py =====
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction
from .models import ExchangeConnection, Balance
from .serializers import ExchangeConnectionSerializer, BalanceSerializer, ExchangeInfoSerializer
from .encryption import encryption_service
from .exchange_service import exchange_service
import logging
import asyncio

logger = logging.getLogger(__name__)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def connect_exchange(request):
    """Connect exchange via API keys"""
    serializer = ExchangeConnectionSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        data = serializer.validated_data
        
        # Encrypt API keys
        encrypted_api_key = encryption_service.encrypt(data['api_key'])
        encrypted_secret = encryption_service.encrypt(data['secret_key'])
        encrypted_passphrase = encryption_service.encrypt(data.get('passphrase', '')) if data.get('passphrase') else None
        
        # Save to database
        with transaction.atomic():
            connection, created = ExchangeConnection.objects.update_or_create(
                user=request.user,
                exchange_id=data['exchange_id'],
                defaults={
                    'api_key_encrypted': encrypted_api_key,
                    'secret_key_encrypted': encrypted_secret,
                    'passphrase_encrypted': encrypted_passphrase,
                    'is_active': True
                }
            )
        
        # Test connection
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(
            exchange_service.connect_exchange(
                str(request.user.id),
                data['exchange_id'],
                data['api_key'],
                data['secret_key'],
                data.get('passphrase')
            )
        )
        
        return Response({
            'success': True,
            'message': f"Connected to {data['exchange_id']}"
        })
    
    except Exception as e:
        logger.error(f"Exchange connection error: {str(e)}")
        return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_balances(request):
    """Get balances from all connected exchanges"""
    try:
        connections = ExchangeConnection.objects.filter(user=request.user, is_active=True)
        
        balances = {}
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        for conn in connections:
            try:
                # Decrypt keys
                api_key = encryption_service.decrypt(conn.api_key_encrypted)
                secret_key = encryption_service.decrypt(conn.secret_key_encrypted)
                
                # Connect and get balance
                loop.run_until_complete(
                    exchange_service.connect_exchange(
                        str(request.user.id),
                        conn.exchange_id,
                        api_key,
                        secret_key
                    )
                )
                
                balance = loop.run_until_complete(
                    exchange_service.get_balance(str(request.user.id), conn.exchange_id)
                )
                balances[conn.exchange_id] = balance['total']
            except Exception as e:
                logger.error(f"Error getting balance from {conn.exchange_id}: {str(e)}")
                balances[conn.exchange_id] = 0
        
        return Response(balances)
    
    except Exception as e:
        return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_available_coins(request):
    """Get available trading pairs for exchange"""
    exchange_id = request.query_params.get('exchange_id')
    if not exchange_id:
        return Response({'detail': 'exchange_id required'}, status=status.HTTP_400_BAD_REQUEST)
    
    # TODO: Implement get_available_pairs
    return Response({'coins': []})

@api_view(['GET'])
def get_supported_exchanges(request):
    """Get list of supported exchanges"""
    EXCHANGE_CONFIG = {
        'binance': {'name': 'Binance', 'tier': 1, 'has': {'spot': True, 'futures': True}, 'fees': {'maker': 0.1, 'taker': 0.1}},
        'gateio': {'name': 'Gate.io', 'tier': 2, 'has': {'spot': True, 'futures': True}, 'fees': {'maker': 0.2, 'taker': 0.2}},
        'bybit': {'name': 'Bybit', 'tier': 2, 'has': {'spot': True, 'futures': True}, 'fees': {'maker': 0.1, 'taker': 0.1}},
    }
    
    exchanges = []
    for exchange_id, config in EXCHANGE_CONFIG.items():
        exchanges.append({
            'id': exchange_id,
            'name': config['name'],
            'tier': config['tier'],
            'has_spot': config['has']['spot'],
            'has_futures': config['has']['futures'],
            'maker_fee': config['fees']['maker'],
            'taker_fee': config['fees']['taker']
        })
    
    return Response({
        'exchanges': sorted(exchanges, key=lambda x: x['tier']),
        'total': len(exchanges)
    })
