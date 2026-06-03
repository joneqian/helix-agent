/**
 * Schema-driven form view — RJSF (antd theme) rendering the AgentSpec JSON
 * Schema. The whole manifest is editable here; ``uiSchema`` nudges layout and
 * routes the model node to the custom ModelSelect field (Stream S PR D). The
 * model catalog (configured providers + models) is loaded once and handed to
 * the field via ``formContext``.
 */
import { useEffect, useState } from "react";
import Form from "@rjsf/antd";
import validator from "@rjsf/validator-ajv8";
import type { IChangeEvent } from "@rjsf/core";
import type { UiSchema } from "@rjsf/utils";

import type { JsonSchema } from "../../api/manifest_schema";
import type { ModelCatalog } from "../../api/model_catalog";
import { loadModelCatalog } from "./catalog";

interface FormViewProps {
  schema: JsonSchema;
  formData: unknown;
  onChange: (data: unknown) => void;
}

const UI_SCHEMA: UiSchema = {
  "ui:submitButtonOptions": { norender: true },
  spec: {
    system_prompt: {
      template: { "ui:widget": "textarea", "ui:options": { rows: 6 } },
    },
  },
};

export function FormView({ schema, formData, onChange }: FormViewProps) {
  const [modelCatalog, setModelCatalog] = useState<ModelCatalog | undefined>(undefined);

  useEffect(() => {
    let alive = true;
    loadModelCatalog().then(
      (c) => {
        if (alive) setModelCatalog(c);
      },
      () => {
        /* catalog optional — the field degrades to a disabled/loading select */
      },
    );
    return () => {
      alive = false;
    };
  }, []);

  return (
    <div data-testid="manifest-form-view">
      <Form
        schema={schema}
        uiSchema={UI_SCHEMA}
        formContext={{ modelCatalog }}
        formData={formData}
        validator={validator}
        liveValidate={false}
        showErrorList={false}
        onChange={(e: IChangeEvent) => onChange(e.formData)}
      />
    </div>
  );
}
