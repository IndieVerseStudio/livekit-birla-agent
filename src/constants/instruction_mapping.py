from types import SimpleNamespace

Instruction = SimpleNamespace(
    KYC_APPROVAL = SimpleNamespace(
        NAME = "KYC_APPROVAL",
        DESCRIPTION = "Customer has issues with KYC approval, account verification, or contractor approval process",
        SRC = "Enhanced_KYC_Approval_Contractor",
    ),
    POINT_REDEMPTION = SimpleNamespace(
        NAME = "POINT_REDEMPTION",
        DESCRIPTION = "Customer cannot redeem points, facing cash withdrawal issues, or redemption errors",
        SRC = "Unable_to_redeem_points"
    ),
    QR_SCANNING = SimpleNamespace(
        NAME = "QR_SCANNING",
        DESCRIPTION = "Customer facing QR code scanning issues, already scanned errors, or invalid barcode problems",
        SRC = "QR_Scanning_Merged"
    ),
    ACCOUNT_BLOCKED = SimpleNamespace(
        NAME = "ACCOUNT_BLOCKED",
        DESCRIPTION = "Customer account is blocked, facing login issues, or access problems",
        SRC = "Painter_Contractor_Account_Blocked"
    ),
    UNCLEAR = SimpleNamespace(
        NAME = "UNCLEAR",
        DESCRIPTION = "Customer intent is not clear from the initial statement",
        SRC = "General_Inquiry"
    )
)