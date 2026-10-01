"""业务模块路由汇总。

这里统一按别名导入再暴露 ROUTERS：模块名有可能和内置名撞车（某个业务模块就叫 dict、list
这种名字时），按名字直接 import 会把内置类型覆盖掉，函数注解在运行时求值就会报
'module' object is not subscriptable。
"""
from __future__ import annotations

from app.routers import register as router_register
from app.routers import regulation as router_regulation
from app.routers import boiler as router_boiler
from app.routers import pressurevessel as router_pressurevessel
from app.routers import pipeline as router_pipeline
from app.routers import elevator as router_elevator
from app.routers import crane as router_crane
from app.routers import forklift as router_forklift
from app.routers import inspection as router_inspection
from app.routers import maintenance as router_maintenance
from app.routers import hazard as router_hazard
from app.routers import accident as router_accident
from app.routers import operator as router_operator
from app.routers import training as router_training
from app.routers import safetyvalve as router_safetyvalve
from app.routers import gauge as router_gauge
from app.routers import sparepart as router_sparepart
from app.routers import emergency as router_emergency
from app.routers import energyeff as router_energyeff
from app.routers import archive as router_archive
from app.routers import contract as router_contract

ROUTERS = [router_register, router_regulation, router_boiler, router_pressurevessel, router_pipeline, router_elevator, router_crane, router_forklift, router_inspection, router_maintenance, router_hazard, router_accident, router_operator, router_training, router_safetyvalve, router_gauge, router_sparepart, router_emergency, router_energyeff, router_archive, router_contract]
