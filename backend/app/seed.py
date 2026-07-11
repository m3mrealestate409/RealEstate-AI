"""
Seed data: default admin + a couple of demo projects with full structured facts.
Idempotent — safe to run on every boot. Lets you test the engine immediately
without a real key (LLM stays in mock mode until you add one).
"""
import logging
from datetime import date

from sqlalchemy import text

from app.config import settings
from app.core.security import hash_password
from app.database import SessionLocal
from app.models import (
    Builder,
    Configuration,
    Inventory,
    Offer,
    Organization,
    PaymentPlan,
    PaymentPlanMilestone,
    Plan,
    Price,
    Project,
    User,
)

logger = logging.getLogger(__name__)


def _seed_plans(db) -> None:
    defaults = [
        {"name": "Basic", "max_employees": 5, "daily_llm_quota": 25, "price_monthly": 0},
        {"name": "Advanced", "max_employees": 25, "daily_llm_quota": 100, "price_monthly": 2999},
        {"name": "Enterprise", "max_employees": 1000, "daily_llm_quota": 1000, "price_monthly": 9999},
    ]
    for p in defaults:
        if not db.query(Plan).filter(Plan.name == p["name"]).first():
            db.add(Plan(**p))
    db.flush()


def _default_org(db) -> Organization:
    org = db.query(Organization).filter(Organization.slug == "chaahat-homes").first()
    if not org:
        advanced = db.query(Plan).filter(Plan.name == "Advanced").first()
        org = Organization(name="Chaahat Homes", slug="chaahat-homes", plan_id=advanced.id)
        db.add(org)
        db.flush()
        logger.info("Seeded default organization: Chaahat Homes")
    return org


def _seed_super_admin(db) -> None:
    if db.query(User).filter(User.email == settings.seed_super_admin_email).first():
        return
    db.add(User(
        email=settings.seed_super_admin_email, name="Platform Owner", role="admin",
        password_hash=hash_password(settings.seed_super_admin_password),
        is_super_admin=True, organization_id=None,
    ))
    logger.info("Seeded super-admin: %s", settings.seed_super_admin_email)


def _seed_admin(db, org: Organization) -> None:
    existing = db.query(User).filter(User.email == settings.seed_admin_email).first()
    if existing:
        if existing.organization_id is None:
            existing.organization_id = org.id  # migrate pre-multitenancy admin
        return
    db.add(User(
        email=settings.seed_admin_email, name="Administrator", role="admin",
        password_hash=hash_password(settings.seed_admin_password),
        organization_id=org.id,
    ))
    logger.info("Seeded org-admin: %s", settings.seed_admin_email)


def _seed_project(
    db, *, org, name, slug, builder, city, locality, status, possession, configs, plan, offer_title
):
    if db.query(Project).filter(Project.slug == slug).first():
        return
    b = db.query(Builder).filter(Builder.name == builder).first()
    if not b:
        b = Builder(name=builder, rera_id=f"RERA-{builder[:3].upper()}-001", organization_id=org.id)
        db.add(b)
        db.flush()

    project = Project(
        name=name, slug=slug, organization_id=org.id, builder_id=b.id, city=city, locality=locality,
        rera_number=f"RERA-{slug[:4].upper()}-2026", project_status=status,
        launch_date=date(2025, 1, 15), possession_date=possession,
    )
    db.add(project)
    db.flush()

    for cfg in configs:
        c = Configuration(
            project_id=project.id, type=cfg["type"], carpet_area=cfg["carpet"],
            super_area=cfg["super"],
        )
        db.add(c)
        db.flush()
        db.add(Price(
            configuration_id=c.id, base_price=cfg["price"], price_unit="per_sqft",
            plc=cfg.get("plc", 0), gst_percent=5, effective_from=date(2026, 7, 1),
            source="Price List Jul-2026",
        ))
        db.add(Inventory(
            configuration_id=c.id, total_units=cfg["total"], available_units=cfg["available"],
        ))

    pp = PaymentPlan(project_id=project.id, name=plan["name"], description=plan["desc"])
    db.add(pp)
    db.flush()
    for i, m in enumerate(plan["milestones"]):
        db.add(PaymentPlanMilestone(payment_plan_id=pp.id, sequence=i, label=m[0], percent=m[1]))

    db.add(Offer(
        project_id=project.id, title=offer_title, details="Limited period launch offer.",
        valid_from=date(2026, 7, 1), valid_to=date(2026, 12, 31), is_active=True,
    ))
    logger.info("Seeded project: %s", name)


_DEFAULT_PASSWORDS = {"admin123", "owner123", "", None}


def _guard_seed_passwords() -> None:
    """H2 — never create the well-known default admin/super-admin accounts in a
    production deployment. Force the operator to set strong seed passwords."""
    if not settings.is_production:
        return
    weak = []
    if settings.seed_admin_password in _DEFAULT_PASSWORDS:
        weak.append("SEED_ADMIN_PASSWORD")
    if settings.seed_super_admin_password in _DEFAULT_PASSWORDS:
        weak.append("SEED_SUPER_ADMIN_PASSWORD")
    if weak:
        raise RuntimeError(
            "Refusing to seed default credentials in production. Set strong values for: "
            + ", ".join(weak)
        )


def seed() -> None:
    _guard_seed_passwords()
    db = SessionLocal()
    try:
        _seed_plans(db)
        org = _default_org(db)
        _seed_super_admin(db)
        _seed_admin(db, org)
        # Migrate any pre-existing rows (created before multi-tenancy) into the
        # default org so nothing is left orphaned.
        db.execute(text(
            "UPDATE users SET organization_id=:oid WHERE organization_id IS NULL AND is_super_admin = false"
        ), {"oid": org.id})
        db.execute(text(
            "UPDATE projects SET organization_id=:oid WHERE organization_id IS NULL"
        ), {"oid": org.id})
        db.execute(text(
            "UPDATE builders SET organization_id=:oid WHERE organization_id IS NULL"
        ), {"oid": org.id})
        db.commit()

        _seed_project(
            db, org=org, name="Golf Hills", slug="golf-hills", builder="Chaahat Developers",
            city="Gurugram", locality="Sector 79", status="Under Construction",
            possession=date(2027, 12, 31),
            configs=[
                {"type": "2BHK", "carpet": 950, "super": 1250, "price": 8500, "plc": 200000, "total": 120, "available": 34},
                {"type": "3BHK", "carpet": 1450, "super": 1850, "price": 9200, "plc": 300000, "total": 80, "available": 21},
            ],
            plan={"name": "10:80:10", "desc": "10% booking, 80% construction-linked, 10% on possession",
                  "milestones": [("On Booking", 10), ("During Construction", 80), ("On Possession", 10)]},
            offer_title="No Floor Rise Charges",
        )
        _seed_project(
            db, org=org, name="Palm Greens", slug="palm-greens", builder="Chaahat Developers",
            city="Gurugram", locality="Sector 88", status="Ready to Move",
            possession=date(2026, 6, 30),
            configs=[
                {"type": "3BHK", "carpet": 1500, "super": 1900, "price": 11000, "plc": 400000, "total": 60, "available": 12},
                {"type": "4BHK", "carpet": 2100, "super": 2600, "price": 12500, "plc": 500000, "total": 30, "available": 8},
            ],
            plan={"name": "Ready-to-Move Plan", "desc": "20% booking, 80% on registry",
                  "milestones": [("On Booking", 20), ("On Registry", 80)]},
            offer_title="Free Modular Kitchen",
        )
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    seed()
