from core.database import db
from admin.models import AdminRole, AdminPermission, AdminRoleModel

def init_admin_roles():
    """Initialize admin roles and permissions in the database."""
    
    # Define role permissions
    role_permissions = {
        AdminRole.SUPER_ADMIN.value: [p.value for p in AdminPermission],  # All permissions
        AdminRole.SUPPORT.value: [
            AdminPermission.VIEW_COMPANIES.value,
            AdminPermission.VIEW_SUPPORT.value,
            AdminPermission.MANAGE_SUPPORT.value
        ],
        AdminRole.ACCOUNTS.value: [
            AdminPermission.VIEW_COMPANIES.value,
            AdminPermission.VIEW_PAYMENTS.value,
            AdminPermission.MANAGE_PAYMENTS.value
        ],
        AdminRole.BACKEND.value: [
            AdminPermission.VIEW_COMPANIES.value,
            AdminPermission.VIEW_APIS.value,
            AdminPermission.MANAGE_APIS.value
        ]
    }
    
    # Create roles if they don't exist
    for role_name, permissions in role_permissions.items():
        role = AdminRoleModel.query.filter_by(name=role_name).first()
        if not role:
            role = AdminRoleModel(
                name=role_name,
                description=f"{role_name.replace('_', ' ').title()} role",
                permissions=permissions
            )
            db.session.add(role)
        else:
            # Update existing role permissions
            role.permissions = permissions
    
    db.session.commit()

if __name__ == "__main__":
    init_admin_roles() 