"""接口出入参模型：列表分页、动作结果与各模块的明细结构。"""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageResult(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int = 1
    size: int = 20


class ActionResult(BaseModel):
    ok: bool
    message: str
    entry: dict[str, Any] | None = None


class EntryPayload(BaseModel):
    """登记或修改一条业务记录时提交的字段集合。"""

    values: dict[str, Any] = Field(default_factory=dict)
    remark: str | None = None


class RegulationPayload(BaseModel):
    """法规条款登记入参。"""

    regulation_code: str
    regulation_name: str
    version: str
    device_category: str
    effective_date: str
    publish_date: str | None = None
    announcement_no: str | None = None
    remark: str | None = None


class RegulationActionPayload(BaseModel):
    """法规条款启用或废止动作。"""

    action: str
    remark: str | None = None



class RegisterEntry(BaseModel):
    """设备登记明细结构。"""

    field_0: str | None = None  # 设备编号
    field_1: str | None = None  # 设备名称
    field_2: str | None = None  # 设备种类
    field_3: str | None = None  # 使用单位
    field_4: str | None = None  # 安装地点
    field_5: str | None = None  # 投用日期
    field_6: str | None = None  # 登记证号
    field_7: str | None = None  # 登记状态

class BoilerEntry(BaseModel):
    """锅炉明细结构。"""

    field_0: str | None = None  # 锅炉编号
    field_1: str | None = None  # 锅炉型号
    field_2: str | None = None  # 额定蒸发量
    field_3: str | None = None  # 工作压力
    field_4: str | None = None  # 燃料类型
    field_5: str | None = None  # 使用年限
    field_6: str | None = None  # 司炉人员
    field_7: str | None = None  # 锅炉状态

class PressurevesselEntry(BaseModel):
    """压力容器明细结构。"""

    field_0: str | None = None  # 容器编号
    field_1: str | None = None  # 容器类别
    field_2: str | None = None  # 设计压力
    field_3: str | None = None  # 工作温度
    field_4: str | None = None  # 介质名称
    field_5: str | None = None  # 容积
    field_6: str | None = None  # 安全附件
    field_7: str | None = None  # 容器状态

class PipelineEntry(BaseModel):
    """压力管道明细结构。"""

    field_0: str | None = None  # 管道编号
    field_1: str | None = None  # 管道级别
    field_2: str | None = None  # 设计压力
    field_3: str | None = None  # 输送介质
    field_4: str | None = None  # 管道长度
    field_5: str | None = None  # 敷设方式
    field_6: str | None = None  # 检验日期
    field_7: str | None = None  # 管道状态

class ElevatorEntry(BaseModel):
    """电梯明细结构。"""

    field_0: str | None = None  # 电梯编号
    field_1: str | None = None  # 电梯类型
    field_2: str | None = None  # 额定载重
    field_3: str | None = None  # 层站数
    field_4: str | None = None  # 维保单位
    field_5: str | None = None  # 上次维保
    field_6: str | None = None  # 下次维保日
    field_7: str | None = None  # 电梯状态

class CraneEntry(BaseModel):
    """起重机明细结构。"""

    field_0: str | None = None  # 起重机编号
    field_1: str | None = None  # 起重机类型
    field_2: str | None = None  # 额定起重量
    field_3: str | None = None  # 跨度
    field_4: str | None = None  # 工作级别
    field_5: str | None = None  # 操作人员
    field_6: str | None = None  # 上次年检
    field_7: str | None = None  # 起重机状态

class ForkliftEntry(BaseModel):
    """场内车辆明细结构。"""

    field_0: str | None = None  # 车辆编号
    field_1: str | None = None  # 车辆类型
    field_2: str | None = None  # 动力类型
    field_3: str | None = None  # 核定载重
    field_4: str | None = None  # 行驶区域
    field_5: str | None = None  # 驾驶员
    field_6: str | None = None  # 年检日期
    field_7: str | None = None  # 车辆状态

class InspectionEntry(BaseModel):
    """检验任务明细结构。"""

    field_0: str | None = None  # 检验编号
    field_1: str | None = None  # 被检设备
    field_2: str | None = None  # 检验类别
    field_3: str | None = None  # 检验机构
    field_4: str | None = None  # 计划检验日
    field_5: str | None = None  # 实际检验日
    field_6: str | None = None  # 检验结论
    field_7: str | None = None  # 检验状态

class MaintenanceEntry(BaseModel):
    """维保记录明细结构。"""

    field_0: str | None = None  # 维保编号
    field_1: str | None = None  # 维保设备
    field_2: str | None = None  # 维保单位
    field_3: str | None = None  # 维保内容
    field_4: str | None = None  # 维保日期
    field_5: str | None = None  # 维保人员
    field_6: str | None = None  # 更换部件
    field_7: str | None = None  # 维保状态

class HazardEntry(BaseModel):
    """隐患记录明细结构。"""

    field_0: str | None = None  # 隐患编号
    field_1: str | None = None  # 所在设备
    field_2: str | None = None  # 隐患类别
    field_3: str | None = None  # 隐患等级
    field_4: str | None = None  # 发现日期
    field_5: str | None = None  # 整改措施
    field_6: str | None = None  # 整改期限
    field_7: str | None = None  # 隐患状态

class AccidentEntry(BaseModel):
    """事故记录明细结构。"""

    field_0: str | None = None  # 事故编号
    field_1: str | None = None  # 事故设备
    field_2: str | None = None  # 事故类型
    field_3: str | None = None  # 伤亡情况
    field_4: str | None = None  # 直接损失
    field_5: str | None = None  # 发生时间
    field_6: str | None = None  # 调查结论
    field_7: str | None = None  # 事故状态

class OperatorEntry(BaseModel):
    """作业人员明细结构。"""

    field_0: str | None = None  # 人员编号
    field_1: str | None = None  # 姓名
    field_2: str | None = None  # 证书类别
    field_3: str | None = None  # 证书编号
    field_4: str | None = None  # 发证日期
    field_5: str | None = None  # 复审日期
    field_6: str | None = None  # 所属单位
    field_7: str | None = None  # 证书状态

class TrainingEntry(BaseModel):
    """培训记录明细结构。"""

    field_0: str | None = None  # 培训编号
    field_1: str | None = None  # 培训内容
    field_2: str | None = None  # 培训对象
    field_3: str | None = None  # 培训日期
    field_4: str | None = None  # 培训讲师
    field_5: str | None = None  # 考核方式
    field_6: str | None = None  # 考核结果
    field_7: str | None = None  # 培训状态

class SafetyvalveEntry(BaseModel):
    """安全阀明细结构。"""

    field_0: str | None = None  # 安全阀编号
    field_1: str | None = None  # 所属设备
    field_2: str | None = None  # 公称通径
    field_3: str | None = None  # 整定压力
    field_4: str | None = None  # 校验日期
    field_5: str | None = None  # 下次校验日
    field_6: str | None = None  # 校验结论
    field_7: str | None = None  # 安全阀状态

class GaugeEntry(BaseModel):
    """压力表明细结构。"""

    field_0: str | None = None  # 压力表编号
    field_1: str | None = None  # 所属设备
    field_2: str | None = None  # 量程范围
    field_3: str | None = None  # 精度等级
    field_4: str | None = None  # 检定日期
    field_5: str | None = None  # 下次检定日
    field_6: str | None = None  # 检定结论
    field_7: str | None = None  # 仪表状态

class SparepartEntry(BaseModel):
    """备件明细结构。"""

    field_0: str | None = None  # 备件编号
    field_1: str | None = None  # 备件名称
    field_2: str | None = None  # 规格型号
    field_3: str | None = None  # 适用设备
    field_4: str | None = None  # 存放位置
    field_5: str | None = None  # 最低保有量
    field_6: str | None = None  # 当前余量
    field_7: str | None = None  # 备件状态

class EmergencyEntry(BaseModel):
    """演练记录明细结构。"""

    field_0: str | None = None  # 演练编号
    field_1: str | None = None  # 演练主题
    field_2: str | None = None  # 演练类型
    field_3: str | None = None  # 参与单位
    field_4: str | None = None  # 演练日期
    field_5: str | None = None  # 演练评估
    field_6: str | None = None  # 改进措施
    field_7: str | None = None  # 演练状态

class EnergyeffEntry(BaseModel):
    """能效记录明细结构。"""

    field_0: str | None = None  # 记录编号
    field_1: str | None = None  # 设备类型
    field_2: str | None = None  # 耗能量
    field_3: str | None = None  # 单耗指标
    field_4: str | None = None  # 对标基准
    field_5: str | None = None  # 偏差比率
    field_6: str | None = None  # 记录月份
    field_7: str | None = None  # 能效状态

class ArchiveEntry(BaseModel):
    """设备档案明细结构。"""

    field_0: str | None = None  # 档案编号
    field_1: str | None = None  # 所属设备
    field_2: str | None = None  # 档案类别
    field_3: str | None = None  # 归档日期
    field_4: str | None = None  # 借阅人
    field_5: str | None = None  # 借阅日期
    field_6: str | None = None  # 归还日期
    field_7: str | None = None  # 档案状态

class ContractEntry(BaseModel):
    """维保合同明细结构。"""

    field_0: str | None = None  # 合同编号
    field_1: str | None = None  # 签约单位
    field_2: str | None = None  # 维保范围
    field_3: str | None = None  # 合同金额
    field_4: str | None = None  # 签约日期
    field_5: str | None = None  # 到期日期
    field_6: str | None = None  # 是否续签
    field_7: str | None = None  # 合同状态
