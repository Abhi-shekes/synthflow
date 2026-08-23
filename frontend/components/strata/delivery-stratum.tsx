"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { AdvancedSection } from "@/components/help/advanced-section";
import { Term } from "@/components/help/term";
import { Stratum } from "@/components/strata/stratum";
import { StreamPreview } from "@/components/stream-preview";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { friendlyError } from "@/lib/friendly-error";
import { api } from "@/lib/api";
import { markChecklistStep } from "@/lib/checklist";
import { useAuthStore } from "@/lib/store";
import type { Entity } from "@/lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";
const WS_URL = API_URL.replace(/^http/, "ws");

/**
 * Everything an entity's rows can be delivered to: REST, WebSocket, Kafka,
 * RabbitMQ, a signed webhook, MQTT, and output plugins.
 *
 * Split out of the entity page rather than left inline. Seven output types is
 * roughly two thirds of that file, and none of it is touched while you are
 * designing a schema — which is what the other three strata are for. Each
 * output owns its own queries, mutations and form state here, so the page above
 * passes three props instead of thirty.
 */
export function DeliveryStratum({
  projectId,
  entityId,
  entity,
  children,
}: {
  projectId: string;
  entityId: string;
  entity: Entity | undefined;
  /** Rendered at the end of the stratum. The page keeps its Generate/export
   * panel here, because that shares `count` and the preview rows with the rest
   * of the page rather than with any one output. */
  children?: React.ReactNode;
}) {
  const accessToken = useAuthStore((s) => s.accessToken);
  const queryClient = useQueryClient();
  // extra isn't installed rather than offer a button that can only 400.
  const installQuery = useQuery({
    queryKey: ["install-config"],
    queryFn: () => api.listInstallConfig(accessToken!),
    enabled: !!accessToken,
  });
  const feature = (key: string) =>
    (installQuery.data ?? []).find((f) => f.key === key);
  const kafkaFeature = feature("kafka");
  const mqttFeature = feature("mqtt");
  // Default to enabled until the query resolves, so the controls don't
  // flicker disabled on every page load.
  const kafkaAvailable = kafkaFeature?.available ?? true;
  const mqttAvailable = mqttFeature?.available ?? true;

  const restOutputsQuery = useQuery({
    queryKey: ["rest-outputs", projectId, entityId],
    queryFn: () => api.listRestOutputs(accessToken!, projectId, entityId),
    enabled: !!accessToken,
  });

  const [restOutputCount, setRestOutputCount] = useState(10);

  const addRestOutput = useMutation({
    mutationFn: () => api.createRestOutput(accessToken!, projectId, entityId, restOutputCount),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["rest-outputs", projectId, entityId] });
      markChecklistStep("delivery");
    },
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not create REST output"),
  });

  const deleteRestOutput = useMutation({
    mutationFn: (outputId: string) => api.deleteRestOutput(accessToken!, projectId, entityId, outputId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["rest-outputs", projectId, entityId] });
    },
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not delete REST output"),
  });

  const streamsQuery = useQuery({
    queryKey: ["websocket-streams", projectId, entityId],
    queryFn: () => api.listWebSocketStreams(accessToken!, projectId, entityId),
    enabled: !!accessToken,
  });

  const [streamEventsPerSecond, setStreamEventsPerSecond] = useState(2);
  const [streamBatchSize, setStreamBatchSize] = useState(1);

  const addStream = useMutation({
    mutationFn: () =>
      api.createWebSocketStream(
        accessToken!,
        projectId,
        entityId,
        streamEventsPerSecond,
        streamBatchSize
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["websocket-streams", projectId, entityId] });
    },
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not create stream"),
  });

  const deleteStream = useMutation({
    mutationFn: (streamId: string) =>
      api.deleteWebSocketStream(accessToken!, projectId, entityId, streamId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["websocket-streams", projectId, entityId] });
    },
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not delete stream"),
  });

  const kafkaOutputsQuery = useQuery({
    queryKey: ["kafka-outputs", projectId, entityId],
    queryFn: () => api.listKafkaOutputs(accessToken!, projectId, entityId),
    enabled: !!accessToken,
  });

  const [kafkaBootstrapServers, setKafkaBootstrapServers] = useState("");
  const [kafkaTopic, setKafkaTopic] = useState("");
  const [kafkaEventsPerSecond, setKafkaEventsPerSecond] = useState(2);
  const [kafkaBatchSize, setKafkaBatchSize] = useState(1);

  const addKafkaOutput = useMutation({
    mutationFn: () =>
      api.createKafkaOutput(accessToken!, projectId, entityId, {
        bootstrap_servers: kafkaBootstrapServers,
        topic: kafkaTopic,
        events_per_second: kafkaEventsPerSecond,
        batch_size: kafkaBatchSize,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["kafka-outputs", projectId, entityId] });
      setKafkaTopic("");
    },
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not create Kafka output"),
  });

  const deleteKafkaOutput = useMutation({
    mutationFn: (outputId: string) =>
      api.deleteKafkaOutput(accessToken!, projectId, entityId, outputId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["kafka-outputs", projectId, entityId] });
    },
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not delete Kafka output"),
  });

  const mqttOutputsQuery = useQuery({
    queryKey: ["mqtt-outputs", projectId, entityId],
    queryFn: () => api.listMqttOutputs(accessToken!, projectId, entityId),
    enabled: !!accessToken,
  });

  const [mqttBrokerHost, setMqttBrokerHost] = useState("");
  const [mqttBrokerPort, setMqttBrokerPort] = useState(1883);
  const [mqttTopic, setMqttTopic] = useState("");
  const [mqttEventsPerSecond, setMqttEventsPerSecond] = useState(2);
  const [mqttBatchSize, setMqttBatchSize] = useState(1);

  const addMqttOutput = useMutation({
    mutationFn: () =>
      api.createMqttOutput(accessToken!, projectId, entityId, {
        broker_host: mqttBrokerHost,
        broker_port: mqttBrokerPort,
        topic: mqttTopic,
        events_per_second: mqttEventsPerSecond,
        batch_size: mqttBatchSize,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["mqtt-outputs", projectId, entityId] });
      setMqttTopic("");
    },
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not create MQTT output"),
  });

  const deleteMqttOutput = useMutation({
    mutationFn: (outputId: string) =>
      api.deleteMqttOutput(accessToken!, projectId, entityId, outputId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["mqtt-outputs", projectId, entityId] });
    },
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not delete MQTT output"),
  });

  const rabbitOutputsQuery = useQuery({
    queryKey: ["rabbitmq-outputs", projectId, entityId],
    queryFn: () => api.listRabbitMQOutputs(accessToken!, projectId, entityId),
    enabled: !!accessToken,
  });

  const [rabbitHost, setRabbitHost] = useState("");
  const [rabbitPort, setRabbitPort] = useState(5672);
  const [rabbitUser, setRabbitUser] = useState("guest");
  const [rabbitPassword, setRabbitPassword] = useState("guest");
  const [rabbitExchange, setRabbitExchange] = useState("");
  const [rabbitRoutingKey, setRabbitRoutingKey] = useState("");
  const [rabbitEventsPerSecond, setRabbitEventsPerSecond] = useState(2);

  const addRabbitOutput = useMutation({
    mutationFn: () =>
      api.createRabbitMQOutput(accessToken!, projectId, entityId, {
        host: rabbitHost,
        port: rabbitPort,
        username: rabbitUser,
        password: rabbitPassword,
        exchange: rabbitExchange,
        routing_key: rabbitRoutingKey,
        events_per_second: rabbitEventsPerSecond,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["rabbitmq-outputs", projectId, entityId] });
      setRabbitRoutingKey("");
    },
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not create RabbitMQ output"),
  });

  const deleteRabbitOutput = useMutation({
    mutationFn: (outputId: string) =>
      api.deleteRabbitMQOutput(accessToken!, projectId, entityId, outputId),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["rabbitmq-outputs", projectId, entityId] }),
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not delete RabbitMQ output"),
  });

  const webhookOutputsQuery = useQuery({
    queryKey: ["webhook-outputs", projectId, entityId],
    queryFn: () => api.listWebhookOutputs(accessToken!, projectId, entityId),
    enabled: !!accessToken,
  });

  const [webhookUrl, setWebhookUrl] = useState("");
  const [webhookSecret, setWebhookSecret] = useState("");
  const [webhookEventsPerSecond, setWebhookEventsPerSecond] = useState(1);
  const [webhookBatchSize, setWebhookBatchSize] = useState(1);

  const addWebhookOutput = useMutation({
    mutationFn: () =>
      api.createWebhookOutput(accessToken!, projectId, entityId, {
        url: webhookUrl,
        secret: webhookSecret,
        events_per_second: webhookEventsPerSecond,
        batch_size: webhookBatchSize,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["webhook-outputs", projectId, entityId] });
      setWebhookUrl("");
      setWebhookSecret("");
    },
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not create webhook output"),
  });

  const deleteWebhookOutput = useMutation({
    mutationFn: (outputId: string) =>
      api.deleteWebhookOutput(accessToken!, projectId, entityId, outputId),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["webhook-outputs", projectId, entityId] }),
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not delete webhook output"),
  });

  const outputPluginsQuery = useQuery({
    queryKey: ["output-plugins"],
    queryFn: () => api.listOutputPlugins(accessToken!),
    enabled: !!accessToken,
  });

  const pluginOutputsQuery = useQuery({
    queryKey: ["plugin-outputs", projectId, entityId],
    queryFn: () => api.listPluginOutputs(accessToken!, projectId, entityId),
    enabled: !!accessToken,
  });

  const [pluginOutputName, setPluginOutputName] = useState("");
  const [pluginOutputConfig, setPluginOutputConfig] = useState("{}");
  const [pluginOutputEventsPerSecond, setPluginOutputEventsPerSecond] = useState(2);
  const [pluginOutputBatchSize, setPluginOutputBatchSize] = useState(1);

  const addPluginOutput = useMutation({
    mutationFn: () => {
      let config: Record<string, unknown>;
      try {
        config = JSON.parse(pluginOutputConfig);
      } catch {
        throw new Error("Config isn't valid JSON");
      }
      return api.createPluginOutput(accessToken!, projectId, entityId, {
        plugin_name: pluginOutputName,
        config,
        events_per_second: pluginOutputEventsPerSecond,
        batch_size: pluginOutputBatchSize,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["plugin-outputs", projectId, entityId] });
    },
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not create plugin output"),
  });

  const deletePluginOutput = useMutation({
    mutationFn: (outputId: string) =>
      api.deletePluginOutput(accessToken!, projectId, entityId, outputId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["plugin-outputs", projectId, entityId] });
    },
    onError: (error: Error) => toast.error(friendlyError(error) || "Could not delete plugin output"),
  });

  // hasContent is always true here: unlike Behaviour/Distortion, Delivery
  // already leads with Generate/Download + REST regardless of mode
  // (SIMPLICITY_PLAN.md Track A.2) — only the non-REST protocols defer, via
  // the nested AdvancedSection below. Letting the outer Stratum also
  // collapse would hide that default-visible content behind a second,
  // redundant click.
  return (
        <Stratum id="delivery" hasContent>
      {children}

      <Panel>
        <PanelHeader>
          <PanelTitle><Term id="rest_output">REST output</Term></PanelTitle>
        </PanelHeader>
        <PanelBody className="flex flex-col gap-4">
          <p className="text-xs leading-relaxed text-ink-dim">
            A public, unauthenticated URL that returns freshly generated rows
            for this entity on every request — point a frontend&apos;s{" "}
            <code className="font-mono">fetch()</code> straight at it during
            development. Anyone with the link can use it, the same as a
            webhook URL.
          </p>
          <div className="flex items-center gap-2">
            <Input
              type="number"
              min={1}
              max={5000}
              value={restOutputCount}
              onChange={(e) => setRestOutputCount(Number(e.target.value))}
              className="w-32"
            />
            <Button
              onClick={() => addRestOutput.mutate()}
              disabled={addRestOutput.isPending || !entity?.fields.length}
            >
              {addRestOutput.isPending ? "Creating…" : "Create endpoint"}
            </Button>
          </div>
          {restOutputsQuery.data?.length === 0 && (
            <p className="text-xs leading-relaxed text-ink-dim">No REST outputs yet.</p>
          )}
          {restOutputsQuery.data && restOutputsQuery.data.length > 0 && (
            <ul className="flex flex-col gap-2">
              {restOutputsQuery.data.map((output) => {
                const url = `${API_URL}/public/rest/${output.token}`;
                return (
                  <li
                    key={output.id}
                    className="flex items-center justify-between gap-2 rounded-md border px-3 py-2 text-sm"
                  >
                    <code className="truncate font-mono">{url}</code>
                    <div className="flex shrink-0 gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          navigator.clipboard.writeText(url);
                          toast.success("Copied");
                        }}
                      >
                        Copy
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => deleteRestOutput.mutate(output.id)}
                      >
                        Delete
                      </Button>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </PanelBody>
      </Panel>

      <AdvancedSection
        label="Advanced delivery — WebSocket, Kafka, RabbitMQ, webhook, MQTT, plugins"
        hasContent={
          (streamsQuery.data?.length ?? 0) > 0 ||
          (kafkaOutputsQuery.data?.length ?? 0) > 0 ||
          (rabbitOutputsQuery.data?.length ?? 0) > 0 ||
          (webhookOutputsQuery.data?.length ?? 0) > 0 ||
          (mqttOutputsQuery.data?.length ?? 0) > 0 ||
          (pluginOutputsQuery.data?.length ?? 0) > 0
        }
      >
      <Panel>
        <PanelHeader>
          <PanelTitle><Term id="websocket_output">Live stream (WebSocket)</Term></PanelTitle>
        </PanelHeader>
        <PanelBody className="flex flex-col gap-4">
          <p className="text-xs leading-relaxed text-ink-dim">
            A public, unauthenticated WebSocket that pushes a fresh batch
            every tick for as long as a client stays connected — no auth,
            no polling. Disconnecting stops production; there&apos;s nothing
            running in the background otherwise.
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-1 text-sm">
              <span className="text-muted-foreground">events/sec</span>
              <Input
                type="number"
                min={0.1}
                max={50}
                step={0.1}
                value={streamEventsPerSecond}
                onChange={(e) => setStreamEventsPerSecond(Number(e.target.value))}
                className="w-20"
              />
            </div>
            <div className="flex items-center gap-1 text-sm">
              <span className="text-muted-foreground">rows/message</span>
              <Input
                type="number"
                min={1}
                max={100}
                value={streamBatchSize}
                onChange={(e) => setStreamBatchSize(Number(e.target.value))}
                className="w-20"
              />
            </div>
            <Button
              onClick={() => addStream.mutate()}
              disabled={addStream.isPending || !entity?.fields.length}
            >
              {addStream.isPending ? "Creating…" : "Create stream"}
            </Button>
          </div>
          {streamsQuery.data?.length === 0 && (
            <p className="text-xs leading-relaxed text-ink-dim">No streams yet.</p>
          )}
          {streamsQuery.data && streamsQuery.data.length > 0 && (
            <ul className="flex flex-col gap-3">
              {streamsQuery.data.map((stream) => {
                const wsUrl = `${WS_URL}/public/stream/${stream.token}`;
                return (
                  <li key={stream.id} className="flex flex-col gap-2">
                    <div className="flex items-center justify-between gap-2 rounded-md border px-3 py-2 text-sm">
                      <code className="truncate font-mono">{wsUrl}</code>
                      <div className="flex shrink-0 gap-2">
                        <span className="text-muted-foreground">
                          {stream.events_per_second}/s × {stream.batch_size}
                        </span>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => deleteStream.mutate(stream.id)}
                        >
                          Delete
                        </Button>
                      </div>
                    </div>
                    <StreamPreview wsUrl={wsUrl} />
                  </li>
                );
              })}
            </ul>
          )}
        </PanelBody>
      </Panel>

      <Panel>
        <PanelHeader>
          <PanelTitle><Term id="kafka_output">Kafka output</Term></PanelTitle>
        </PanelHeader>
        <PanelBody className="flex flex-col gap-4">
          <p className="text-xs leading-relaxed text-ink-dim">
            Publishes a fresh row to a Kafka topic every tick, for as long
            as the backend process runs — a real background producer, not
            tied to a client connection, so it keeps going after you leave
            this page. Doesn&apos;t survive a backend restart yet (a known
            gap, not a silent one); delete and recreate it if that happens.
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <Input
              placeholder="bootstrap servers, e.g. kafka:9092"
              value={kafkaBootstrapServers}
              onChange={(e) => setKafkaBootstrapServers(e.target.value)}
              className="w-56"
            />
            <Input
              placeholder="topic"
              value={kafkaTopic}
              onChange={(e) => setKafkaTopic(e.target.value)}
              className="w-32"
            />
            <div className="flex items-center gap-1 text-sm">
              <span className="text-muted-foreground">events/sec</span>
              <Input
                type="number"
                min={0.1}
                max={50}
                step={0.1}
                value={kafkaEventsPerSecond}
                onChange={(e) => setKafkaEventsPerSecond(Number(e.target.value))}
                className="w-20"
              />
            </div>
            <div className="flex items-center gap-1 text-sm">
              <span className="text-muted-foreground">rows/message</span>
              <Input
                type="number"
                min={1}
                max={100}
                value={kafkaBatchSize}
                onChange={(e) => setKafkaBatchSize(Number(e.target.value))}
                className="w-20"
              />
            </div>
            <Button
              onClick={() => addKafkaOutput.mutate()}
              disabled={
                addKafkaOutput.isPending ||
                !entity?.fields.length ||
                !kafkaBootstrapServers ||
                !kafkaTopic ||
                !kafkaAvailable
              }
            >
              {addKafkaOutput.isPending ? "Creating…" : "Create output"}
            </Button>
          </div>
          {!kafkaAvailable && (
            <p className="rounded-md border border-dashed px-3 py-2 text-xs text-ink-dim">
              Not available in this install — the optional{" "}
              <code className="font-mono">{kafkaFeature?.extra ?? "kafka"}</code> extra
              isn&apos;t installed. Run{" "}
              <code className="font-mono">synthflow init --services kafka</code>, then
              rebuild the backend to enable it.
            </p>
          )}
          {kafkaOutputsQuery.data?.length === 0 && (
            <p className="text-xs leading-relaxed text-ink-dim">No Kafka outputs yet.</p>
          )}
          {kafkaOutputsQuery.data && kafkaOutputsQuery.data.length > 0 && (
            <ul className="flex flex-col gap-2">
              {kafkaOutputsQuery.data.map((output) => (
                <li
                  key={output.id}
                  className="flex items-center justify-between gap-2 rounded-md border px-3 py-2 text-sm"
                >
                  <code className="truncate font-mono">
                    {output.bootstrap_servers} → {output.topic}
                  </code>
                  <div className="flex shrink-0 items-center gap-2">
                    <span className="text-muted-foreground">
                      {output.events_per_second}/s × {output.batch_size}
                    </span>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => deleteKafkaOutput.mutate(output.id)}
                    >
                      Delete
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </PanelBody>
      </Panel>

      <Panel>
        <PanelHeader>
          <PanelTitle><Term id="rabbitmq_output">RabbitMQ output</Term></PanelTitle>
        </PanelHeader>
        <PanelBody className="flex flex-col gap-4">
          <p className="text-xs leading-relaxed text-ink-dim">
            A background producer publishing one JSON message per row to a
            RabbitMQ exchange. Leave the exchange blank to use the default
            one, where the routing key is the queue name —{" "}
            <strong>note that RabbitMQ silently discards messages whose
            queue does not exist yet</strong>, so declare the queue first
            or the messages go nowhere.
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <Input placeholder="host" value={rabbitHost}
              onChange={(e) => setRabbitHost(e.target.value)} className="w-36" />
            <Input type="number" placeholder="port" value={rabbitPort}
              onChange={(e) => setRabbitPort(Number(e.target.value))} className="w-24" />
            <Input placeholder="username" value={rabbitUser}
              onChange={(e) => setRabbitUser(e.target.value)} className="w-32" />
            <Input type="password" placeholder="password" value={rabbitPassword}
              onChange={(e) => setRabbitPassword(e.target.value)} className="w-32" />
            <Input placeholder="exchange (blank = default)" value={rabbitExchange}
              onChange={(e) => setRabbitExchange(e.target.value)} className="w-48" />
            <Input placeholder="routing key / queue" value={rabbitRoutingKey}
              onChange={(e) => setRabbitRoutingKey(e.target.value)} className="w-44" />
            <Input type="number" placeholder="events/sec" value={rabbitEventsPerSecond}
              onChange={(e) => setRabbitEventsPerSecond(Number(e.target.value))} className="w-28" />
            <Button onClick={() => addRabbitOutput.mutate()}
              disabled={addRabbitOutput.isPending || !rabbitHost || !rabbitRoutingKey}>
              {addRabbitOutput.isPending ? "Creating…" : "Create output"}
            </Button>
          </div>
          {rabbitOutputsQuery.data?.length === 0 && (
            <p className="text-xs leading-relaxed text-ink-dim">No RabbitMQ outputs yet.</p>
          )}
          {rabbitOutputsQuery.data && rabbitOutputsQuery.data.length > 0 && (
            <ul className="flex flex-col gap-2">
              {rabbitOutputsQuery.data.map((output) => (
                <li key={output.id}
                  className="flex items-center justify-between rounded-md border px-3 py-2 text-sm">
                  <span className="font-mono text-xs">
                    {output.host}:{output.port} {output.exchange || "(default)"} →{" "}
                    {output.routing_key} @ {output.events_per_second}/s
                  </span>
                  <Button variant="ghost" size="sm"
                    onClick={() => deleteRabbitOutput.mutate(output.id)}>
                    Delete
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </PanelBody>
      </Panel>

      <Panel>
        <PanelHeader>
          <PanelTitle><Term id="webhook_output">Signed webhook output</Term></PanelTitle>
        </PanelHeader>
        <PanelBody className="flex flex-col gap-4">
          <p className="text-xs leading-relaxed text-ink-dim">
            POSTs a batch of rows to your URL on every tick. Each request
            carries an <code className="font-mono">X-SynthFlow-Signature</code>{" "}
            header — an HMAC-SHA256 of the timestamp and the exact body,
            using the secret below — so the receiver can prove the request
            came from you rather than trusting a URL nobody else is meant
            to know. The timestamp is inside the signed value, so a captured
            request cannot be replayed later.
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <Input placeholder="https://example.com/hook" value={webhookUrl}
              onChange={(e) => setWebhookUrl(e.target.value)} className="w-72" />
            <Input type="password" placeholder="shared secret" value={webhookSecret}
              onChange={(e) => setWebhookSecret(e.target.value)} className="w-44" />
            <Input type="number" placeholder="events/sec" value={webhookEventsPerSecond}
              onChange={(e) => setWebhookEventsPerSecond(Number(e.target.value))} className="w-28" />
            <Input type="number" placeholder="rows/request" value={webhookBatchSize}
              onChange={(e) => setWebhookBatchSize(Number(e.target.value))} className="w-28" />
            <Button onClick={() => addWebhookOutput.mutate()}
              disabled={addWebhookOutput.isPending || !webhookUrl || !webhookSecret}>
              {addWebhookOutput.isPending ? "Creating…" : "Create webhook"}
            </Button>
          </div>
          {webhookOutputsQuery.data?.length === 0 && (
            <p className="text-xs leading-relaxed text-ink-dim">No webhooks yet.</p>
          )}
          {webhookOutputsQuery.data && webhookOutputsQuery.data.length > 0 && (
            <ul className="flex flex-col gap-2">
              {webhookOutputsQuery.data.map((output) => (
                <li key={output.id}
                  className="flex items-center justify-between rounded-md border px-3 py-2 text-sm">
                  <span className="font-mono text-xs">
                    POST {output.url} — {output.batch_size} row(s) @{" "}
                    {output.events_per_second}/s
                  </span>
                  <Button variant="ghost" size="sm"
                    onClick={() => deleteWebhookOutput.mutate(output.id)}>
                    Delete
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </PanelBody>
      </Panel>

      <Panel>
        <PanelHeader>
          <PanelTitle><Term id="mqtt_output">MQTT output</Term></PanelTitle>
        </PanelHeader>
        <PanelBody className="flex flex-col gap-4">
          <p className="text-xs leading-relaxed text-ink-dim">
            Same idea as the Kafka output above, publishing to an MQTT
            broker instead — a real background producer that keeps
            running independent of any client connection.
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <Input
              placeholder="broker host"
              value={mqttBrokerHost}
              onChange={(e) => setMqttBrokerHost(e.target.value)}
              className="w-40"
            />
            <Input
              type="number"
              min={1}
              max={65535}
              value={mqttBrokerPort}
              onChange={(e) => setMqttBrokerPort(Number(e.target.value))}
              className="w-24"
            />
            <Input
              placeholder="topic"
              value={mqttTopic}
              onChange={(e) => setMqttTopic(e.target.value)}
              className="w-32"
            />
            <div className="flex items-center gap-1 text-sm">
              <span className="text-muted-foreground">events/sec</span>
              <Input
                type="number"
                min={0.1}
                max={50}
                step={0.1}
                value={mqttEventsPerSecond}
                onChange={(e) => setMqttEventsPerSecond(Number(e.target.value))}
                className="w-20"
              />
            </div>
            <div className="flex items-center gap-1 text-sm">
              <span className="text-muted-foreground">rows/message</span>
              <Input
                type="number"
                min={1}
                max={100}
                value={mqttBatchSize}
                onChange={(e) => setMqttBatchSize(Number(e.target.value))}
                className="w-20"
              />
            </div>
            <Button
              onClick={() => addMqttOutput.mutate()}
              disabled={
                addMqttOutput.isPending ||
                !entity?.fields.length ||
                !mqttBrokerHost ||
                !mqttTopic ||
                !mqttAvailable
              }
            >
              {addMqttOutput.isPending ? "Creating…" : "Create output"}
            </Button>
          </div>
          {!mqttAvailable && (
            <p className="rounded-md border border-dashed px-3 py-2 text-xs text-ink-dim">
              Not available in this install — the optional{" "}
              <code className="font-mono">{mqttFeature?.extra ?? "mqtt"}</code> extra
              isn&apos;t installed. Run{" "}
              <code className="font-mono">synthflow init --services mqtt</code>, then
              rebuild the backend to enable it.
            </p>
          )}
          {mqttOutputsQuery.data?.length === 0 && (
            <p className="text-xs leading-relaxed text-ink-dim">No MQTT outputs yet.</p>
          )}
          {mqttOutputsQuery.data && mqttOutputsQuery.data.length > 0 && (
            <ul className="flex flex-col gap-2">
              {mqttOutputsQuery.data.map((output) => (
                <li
                  key={output.id}
                  className="flex items-center justify-between gap-2 rounded-md border px-3 py-2 text-sm"
                >
                  <code className="truncate font-mono">
                    {output.broker_host}:{output.broker_port} → {output.topic}
                  </code>
                  <div className="flex shrink-0 items-center gap-2">
                    <span className="text-muted-foreground">
                      {output.events_per_second}/s × {output.batch_size}
                    </span>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => deleteMqttOutput.mutate(output.id)}
                    >
                      Delete
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </PanelBody>
      </Panel>

      <Panel>
        <PanelHeader>
          <PanelTitle><Term id="plugin_output">Plugin output</Term></PanelTitle>
        </PanelHeader>
        <PanelBody className="flex flex-col gap-4">
          <p className="text-xs leading-relaxed text-ink-dim">
            Same background-producer idea as Kafka/MQTT above, but delivering
            through a third-party output plugin instead of a built-in
            broker — install one (see the{" "}
            <code className="font-mono">examples/example-plugin</code>{" "}
            package) to pick it here. Config is whatever free-form JSON
            that plugin expects.
          </p>
          <div className="flex flex-wrap items-start gap-2">
            <Select
              value={pluginOutputName}
              onValueChange={(v) => setPluginOutputName(v ?? "")}
            >
              <SelectTrigger className="w-48">
                <SelectValue placeholder="plugin" />
              </SelectTrigger>
              <SelectContent>
                {outputPluginsQuery.data?.map((p) => (
                  <SelectItem key={p.name} value={p.name}>
                    {p.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Textarea
              placeholder='config, e.g. {"path": "/tmp/out.jsonl"}'
              value={pluginOutputConfig}
              onChange={(e) => setPluginOutputConfig(e.target.value)}
              className="h-9 min-h-9 w-56"
            />
            <div className="flex items-center gap-1 text-sm">
              <span className="text-muted-foreground">events/sec</span>
              <Input
                type="number"
                min={0.1}
                max={50}
                step={0.1}
                value={pluginOutputEventsPerSecond}
                onChange={(e) => setPluginOutputEventsPerSecond(Number(e.target.value))}
                className="w-20"
              />
            </div>
            <div className="flex items-center gap-1 text-sm">
              <span className="text-muted-foreground">rows/message</span>
              <Input
                type="number"
                min={1}
                max={100}
                value={pluginOutputBatchSize}
                onChange={(e) => setPluginOutputBatchSize(Number(e.target.value))}
                className="w-20"
              />
            </div>
            <Button
              onClick={() => addPluginOutput.mutate()}
              disabled={
                addPluginOutput.isPending || !entity?.fields.length || !pluginOutputName
              }
            >
              {addPluginOutput.isPending ? "Creating…" : "Create output"}
            </Button>
          </div>
          {outputPluginsQuery.data?.length === 0 && (
            <p className="text-xs leading-relaxed text-ink-dim">
              No output plugins installed yet.
            </p>
          )}
          {pluginOutputsQuery.data?.length === 0 && (
            <p className="text-xs leading-relaxed text-ink-dim">No plugin outputs yet.</p>
          )}
          {pluginOutputsQuery.data && pluginOutputsQuery.data.length > 0 && (
            <ul className="flex flex-col gap-2">
              {pluginOutputsQuery.data.map((output) => (
                <li
                  key={output.id}
                  className="flex items-center justify-between gap-2 rounded-md border px-3 py-2 text-sm"
                >
                  <code className="truncate font-mono">
                    {output.plugin_name} {JSON.stringify(output.config)}
                  </code>
                  <div className="flex shrink-0 items-center gap-2">
                    <span className="text-muted-foreground">
                      {output.events_per_second}/s × {output.batch_size}
                    </span>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => deletePluginOutput.mutate(output.id)}
                    >
                      Delete
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </PanelBody>
      </Panel>
      </AdvancedSection>
    </Stratum>
  );
}
