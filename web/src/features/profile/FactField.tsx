import { Controller, type Control, type UseFormRegister } from 'react-hook-form'

import type { Fact, FactDefinition } from '@/api/profile'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'

import type { SectionFormValues } from './factForm'

type Props = {
  definition: FactDefinition
  stored: Fact | undefined
  register: UseFormRegister<SectionFormValues>
  control: Control<SectionFormValues>
  error: string | undefined
}

const ORIGIN_LABELS: Record<Fact['origin'], string> = {
  questionnaire: 'From onboarding',
  resume: 'From your resume',
  scholarship_answer: 'Answered for a scholarship',
  manual: 'Entered by you',
}

/** One catalog fact as an accessible form field (label, help, error). */
export function FactField({
  definition: d,
  stored,
  register,
  control,
  error,
}: Props) {
  const id = `fact-${d.key}`
  const helpId = `${id}-help`
  const errorId = `${id}-error`
  const describedBy =
    [d.help && helpId, error && errorId].filter(Boolean).join(' ') || undefined
  const common = {
    id,
    'aria-invalid': error ? true : undefined,
    'aria-describedby': describedBy,
  }

  return (
    <div className="space-y-1.5">
      {d.type === 'multi_choice' ? (
        <fieldset aria-describedby={describedBy}>
          <legend className="text-sm font-medium">
            {d.label}
            <SensitiveHint show={d.sensitive} />
          </legend>
          <Controller
            control={control}
            name={d.key}
            render={({ field }) => {
              const checked = Array.isArray(field.value) ? field.value : []
              return (
                <div className="mt-2 grid gap-2 sm:grid-cols-2">
                  {d.choices.map((choice) => (
                    <label
                      key={choice.value}
                      className="flex items-center gap-2 text-sm"
                    >
                      <input
                        type="checkbox"
                        className="size-4 accent-primary"
                        checked={checked.includes(choice.value)}
                        onChange={(e) =>
                          field.onChange(
                            e.target.checked
                              ? [...checked, choice.value]
                              : checked.filter((v) => v !== choice.value),
                          )
                        }
                        onBlur={field.onBlur}
                      />
                      {choice.label}
                    </label>
                  ))}
                </div>
              )
            }}
          />
        </fieldset>
      ) : (
        <>
          <Label htmlFor={id}>
            {d.label}
            <SensitiveHint show={d.sensitive} />
          </Label>
          {d.type === 'boolean' || d.type === 'choice' ? (
            <NativeSelect className="w-full" {...common} {...register(d.key)}>
              <NativeSelectOption value="">Not set</NativeSelectOption>
              {d.type === 'boolean' ? (
                <>
                  <NativeSelectOption value="true">Yes</NativeSelectOption>
                  <NativeSelectOption value="false">No</NativeSelectOption>
                </>
              ) : (
                d.choices.map((c) => (
                  <NativeSelectOption key={c.value} value={c.value}>
                    {c.label}
                  </NativeSelectOption>
                ))
              )}
            </NativeSelect>
          ) : (
            <Input
              {...common}
              {...register(d.key)}
              type={d.type === 'date' ? 'date' : 'text'}
              // Text inputs (not type="number") so the browser never silently
              // drops what was typed; validation explains any problem instead.
              inputMode={
                d.type === 'integer'
                  ? 'numeric'
                  : d.type === 'number'
                    ? 'decimal'
                    : undefined
              }
            />
          )}
        </>
      )}
      {d.help && (
        <p id={helpId} className="text-xs text-muted-foreground">
          {d.help}
        </p>
      )}
      {error && (
        <p id={errorId} role="alert" className="text-xs text-destructive">
          {error}
        </p>
      )}
      {stored && (
        <p className="text-xs text-muted-foreground">
          {ORIGIN_LABELS[stored.origin]}
          {stored.origin_detail && ` (${stored.origin_detail})`}
        </p>
      )}
    </div>
  )
}

/** Marks sensitive facts as optional right where they're asked (FR-P6). */
function SensitiveHint({ show }: { show: boolean }) {
  if (!show) return null
  // A real space (not just CSS margin) so screen readers don't run the
  // label and the hint together.
  return (
    <>
      {' '}
      <span className="text-xs font-normal text-muted-foreground">
        (optional, sensitive)
      </span>
    </>
  )
}
