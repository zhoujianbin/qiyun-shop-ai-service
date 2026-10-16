import Col from 'antd/es/col';
import Form from 'antd/es/form';
import Input from 'antd/es/input';
import Row from 'antd/es/row';
import Switch from 'antd/es/switch';
import type { FormInstance } from 'antd';

export interface AddressFormProps {
  form: FormInstance;
  disabled?: boolean;
  showDefault?: boolean;
}

/** 地址表单：收件人/手机/省市区/详址必填；手机 11 位。 */
export function AddressForm({ form, disabled, showDefault = true }: AddressFormProps) {
  return (
    <Form form={form} layout="vertical" disabled={disabled}>
      <Row gutter={16}>
        <Col span={12}>
          <Form.Item label="收件人" name="receiver_name" rules={[{ required: true, message: '请输入收件人' }, { max: 32, message: '不超过 32 字' }]}>
            <Input placeholder="请输入收件人姓名" />
          </Form.Item>
        </Col>
        <Col span={12}>
          <Form.Item
            label="手机号"
            name="receiver_mobile"
            rules={[
              { required: true, message: '请输入手机号' },
              { pattern: /^1[3-9]\d{9}$/, message: '请输入 11 位大陆手机号' },
            ]}
          >
            <Input placeholder="11 位手机号" maxLength={11} inputMode="numeric" />
          </Form.Item>
        </Col>
        <Col span={8}>
          <Form.Item label="省" name="province" rules={[{ required: true, message: '请输入省' }]}>
            <Input placeholder="如：浙江省" />
          </Form.Item>
        </Col>
        <Col span={8}>
          <Form.Item label="市" name="city" rules={[{ required: true, message: '请输入市' }]}>
            <Input placeholder="如：杭州市" />
          </Form.Item>
        </Col>
        <Col span={8}>
          <Form.Item label="区/县" name="district" rules={[{ required: true, message: '请输入区/县' }]}>
            <Input placeholder="如：西湖区" />
          </Form.Item>
        </Col>
        <Col span={24}>
          <Form.Item label="详细地址" name="detail" rules={[{ required: true, message: '请输入详细地址' }, { max: 200, message: '不超过 200 字' }]}>
            <Input.TextArea rows={2} placeholder="街道、门牌号、楼栋房号" />
          </Form.Item>
        </Col>
        <Col span={12}>
          <Form.Item label="邮编" name="postal_code" rules={[{ pattern: /^\d{6}$/, message: '请输入 6 位邮编' }]}>
            <Input placeholder="选填" maxLength={6} inputMode="numeric" />
          </Form.Item>
        </Col>
        {showDefault ? (
          <Col span={12}>
            <Form.Item label="设为默认地址" name="is_default" valuePropName="checked">
              <Switch />
            </Form.Item>
          </Col>
        ) : null}
      </Row>
    </Form>
  );
}
