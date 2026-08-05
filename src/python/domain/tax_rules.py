from enum import Enum
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, List
from datetime import date


class SupplyTaxStatus(Enum):
    TAXABLE = "Taxable"
    ZERO_RATED = "Zero-rated"
    EXEMPT = "Exempt"
    OUT_OF_SCOPE = "Out of Scope"
    REVIEW_REQUIRED = "Review Required"


class ContextType(Enum):
    BUSINESS_UNIT = "BusinessUnit"
    HOUSEHOLD = "Household"


@dataclass
class ReportingContext:
    context_type: ContextType
    context_id: str
    owner: str


@dataclass
class TaxConfiguration:
    config_id: str
    reporting_context: ReportingContext
    effective_from: date
    effective_to: Optional[date]
    supply_status: SupplyTaxStatus
    is_hst_registrant: bool
    itc_eligible_percentage: Decimal
    quarterly_hst_inclusion: bool
    description: str


class ConfigurationRegistry:
    def __init__(self):
        self._configs: List[TaxConfiguration] = []

    def register(self, config: TaxConfiguration) -> None:
        if config.effective_to and config.effective_to < config.effective_from:
            raise ValueError("End date cannot precede start date.")
            
        # Check for overlaps
        for existing in self._configs:
            if existing.reporting_context.context_id == config.reporting_context.context_id:
                # Check date overlap
                latest_start = max(existing.effective_from, config.effective_from)
                
                end_e = existing.effective_to or date.max
                end_c = config.effective_to or date.max
                earliest_end = min(end_e, end_c)
                
                if latest_start <= earliest_end:
                    raise ValueError(f"Overlapping configuration for {config.reporting_context.context_id}")
                    
        self._configs.append(config)

    def resolve(self, context_id: str, transaction_date: date) -> Optional[TaxConfiguration]:
        for config in self._configs:
            if config.reporting_context.context_id == context_id:
                end_date = config.effective_to or date.max
                if config.effective_from <= transaction_date <= end_date:
                    return config
        return None


@dataclass
class TransactionTaxDetail:
    subtotal: Decimal
    tax_charged_by_vendor: Decimal
    supply_status: SupplyTaxStatus
    itc_eligible_percentage: Decimal
    override_reason: Optional[str] = None
    applied_config_id: Optional[str] = None
    
    @property
    def itc_eligible_amount(self) -> Decimal:
        return (self.tax_charged_by_vendor * self.itc_eligible_percentage).quantize(Decimal("0.01"))
        
    @property
    def non_creditable_tax(self) -> Decimal:
        return self.tax_charged_by_vendor - self.itc_eligible_amount
        
    @property
    def full_expense_cost(self) -> Decimal:
        return self.subtotal + self.non_creditable_tax


def calculate_tax_detail(
    subtotal: str | float, 
    tax_charged: str | float, 
    transaction_date: date,
    context_id: str,
    registry: ConfigurationRegistry,
    override_status: Optional[SupplyTaxStatus] = None,
    override_itc_percentage: Optional[str | float] = None,
    override_reason: Optional[str] = None
) -> TransactionTaxDetail:
    """Calculates tax details resolving the effective-dated configuration."""
    sub_dec = Decimal(str(subtotal))
    tax_dec = Decimal(str(tax_charged))
    
    if (override_status or override_itc_percentage is not None) and not override_reason:
        raise ValueError("An explicit advanced override requires an override_reason.")
        
    config = registry.resolve(context_id, transaction_date)
    
    if not config:
        return TransactionTaxDetail(
            subtotal=sub_dec,
            tax_charged_by_vendor=tax_dec,
            supply_status=SupplyTaxStatus.REVIEW_REQUIRED,
            itc_eligible_percentage=Decimal("0.00"),
            override_reason="Missing configuration",
            applied_config_id=None
        )
    
    status = override_status if override_status else config.supply_status
    itc_pct = Decimal(str(override_itc_percentage)) if override_itc_percentage is not None else config.itc_eligible_percentage
    
    return TransactionTaxDetail(
        subtotal=sub_dec,
        tax_charged_by_vendor=tax_dec,
        supply_status=status,
        itc_eligible_percentage=itc_pct,
        override_reason=override_reason,
        applied_config_id=config.config_id
    )

# Standard defaults
HOUSEHOLD_CONTEXT = ReportingContext(ContextType.HOUSEHOLD, "family_household", "Family")
DEBORAH_PRIVATE_CONTEXT = ReportingContext(ContextType.BUSINESS_UNIT, "deborah_ot_private", "Deborah")
DEBORAH_VHA_CONTEXT = ReportingContext(ContextType.BUSINESS_UNIT, "deborah_ot_vha", "Deborah")
CORY_BUSINESS_CONTEXT = ReportingContext(ContextType.BUSINESS_UNIT, "cory_business", "Cory")
LEGAL_PRACTICE_CONTEXT = ReportingContext(ContextType.BUSINESS_UNIT, "legal_practice", "Cory")

def populate_default_registry(registry: ConfigurationRegistry) -> None:
    # Open-ended current configurations
    registry.register(TaxConfiguration(
        config_id="family_default_v1",
        reporting_context=HOUSEHOLD_CONTEXT,
        effective_from=date(1970, 1, 1),
        effective_to=None,
        supply_status=SupplyTaxStatus.OUT_OF_SCOPE,
        is_hst_registrant=False,
        itc_eligible_percentage=Decimal("0.00"),
        quarterly_hst_inclusion=False,
        description="Ordinary household spending."
    ))

    registry.register(TaxConfiguration(
        config_id="deb_private_default_v1",
        reporting_context=DEBORAH_PRIVATE_CONTEXT,
        effective_from=date(1970, 1, 1),
        effective_to=None,
        supply_status=SupplyTaxStatus.EXEMPT,
        is_hst_registrant=False,
        itc_eligible_percentage=Decimal("0.00"),
        quarterly_hst_inclusion=False,
        description="Exempt occupational therapy services."
    ))

    registry.register(TaxConfiguration(
        config_id="deb_vha_default_v1",
        reporting_context=DEBORAH_VHA_CONTEXT,
        effective_from=date(1970, 1, 1),
        effective_to=None,
        supply_status=SupplyTaxStatus.EXEMPT,
        is_hst_registrant=False,
        itc_eligible_percentage=Decimal("0.00"),
        quarterly_hst_inclusion=False,
        description="Exempt occupational therapy services."
    ))

    registry.register(TaxConfiguration(
        config_id="cory_business_default_v1",
        reporting_context=CORY_BUSINESS_CONTEXT,
        effective_from=date(1970, 1, 1),
        effective_to=None,
        supply_status=SupplyTaxStatus.TAXABLE,
        is_hst_registrant=True,
        itc_eligible_percentage=Decimal("1.00"),
        quarterly_hst_inclusion=True,
        description="Taxable business services."
    ))
    
    registry.register(TaxConfiguration(
        config_id="legal_practice_default_v1",
        reporting_context=LEGAL_PRACTICE_CONTEXT,
        effective_from=date(1970, 1, 1),
        effective_to=None,
        supply_status=SupplyTaxStatus.TAXABLE,
        is_hst_registrant=True,
        itc_eligible_percentage=Decimal("1.00"),
        quarterly_hst_inclusion=True,
        description="Taxable legal services."
    ))
